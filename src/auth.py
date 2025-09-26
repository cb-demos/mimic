"""User authentication services for the cleanup system."""

import logging

from src.config import settings
from src.database import get_database
from src.security import NoValidPATFoundError, get_pat_manager

logger = logging.getLogger(__name__)


class AuthService:
    """Handles user authentication and PAT management."""

    def __init__(self):
        self.db = get_database()
        self.pat_manager = get_pat_manager()

    async def store_user_tokens(
        self,
        email: str,
        unify_pat: str,
        github_pat: str | None = None,
        name: str | None = None,
    ) -> dict:
        """Store user tokens securely, avoiding duplicates.

        Args:
            email: User's company email address
            unify_pat: CloudBees Unify PAT
            github_pat: Optional GitHub PAT
            name: Optional display name

        Returns:
            User details dictionary with auth tokens
        """
        # Normalize email to lowercase
        email = email.lower().strip()

        # Store user record
        await self.db.create_user(email, name)

        # Handle CloudBees PAT - check for existing before storing
        cloudbees_token = await self._store_pat_if_new(email, unify_pat, "cloudbees")

        # Handle GitHub PAT if provided
        github_token = None
        if github_pat:
            github_token = await self._store_pat_if_new(email, github_pat, "github")

        logger.info(f"Successfully stored/updated tokens for {email}")

        return {
            "email": email,
            "name": name,
            "cloudbees_token": str(cloudbees_token),
            "github_token": str(github_token) if github_token else None,
            "has_github_pat": bool(github_pat)
        }

    async def _store_pat_if_new(self, email: str, pat: str, platform: str) -> int:
        """Store PAT only if it doesn't already exist for this user.

        Args:
            email: User's email
            pat: Plain text PAT
            platform: Platform ('cloudbees' or 'github')

        Returns:
            The database ID (token) of the PAT
        """
        # Check if this exact PAT already exists for this user
        existing_pats = await self.db.get_user_pats(email, platform)

        for pat_record in existing_pats:
            try:
                decrypted_pat = self.pat_manager.decrypt(pat_record["encrypted_pat"])
                if decrypted_pat == pat:
                    # PAT already exists, just update last_used
                    await self.db.update_pat_last_used(pat_record["id"])
                    logger.info(f"Found existing {platform} PAT for {email}, updated last_used")
                    return pat_record["id"]
            except Exception as e:
                # Failed to decrypt - mark as inactive and continue
                logger.warning(f"Failed to decrypt existing PAT for {email}: {e}")
                await self.db.mark_pat_inactive(pat_record["id"])

        # PAT doesn't exist, store it
        encrypted_pat = self.pat_manager.encrypt(pat)
        pat_id = await self.db.store_pat(email, encrypted_pat, platform)
        logger.info(f"Stored new {platform} PAT for {email} with token {pat_id}")
        return pat_id

    async def get_pat(self, email: str, platform: str = "cloudbees") -> str:
        """Get the appropriate PAT for a user and platform.

        Logic:
        - CloudBees: Always use user's PAT (required)
        - GitHub: Use user's PAT if they have one, otherwise use system default

        Args:
            email: User's email
            platform: Platform ('cloudbees' or 'github')

        Returns:
            PAT string to use

        Raises:
            NoValidPATFoundError: If no valid PAT is available
        """
        email = email.lower().strip()

        # For CloudBees, always use user PAT (required)
        if platform == "cloudbees":
            pats = await self.db.get_user_pats(email, platform)
            if not pats:
                raise NoValidPATFoundError(f"No CloudBees PAT found for user {email}")

            # Return the most recent PAT (first in the ordered list)
            most_recent_pat = pats[0]
            return self.pat_manager.decrypt(most_recent_pat["encrypted_pat"])

        # For GitHub: user PAT if available, otherwise system default
        elif platform == "github":
            pats = await self.db.get_user_pats(email, platform)

            # If user has a GitHub PAT, use it
            if pats:
                try:
                    most_recent_pat = pats[0]
                    return self.pat_manager.decrypt(most_recent_pat["encrypted_pat"])
                except Exception as e:
                    logger.warning(
                        f"Failed to decrypt user GitHub PAT for {email}: {e}"
                    )
                    # Fall through to system default

            # Use system default GitHub token
            if settings.GITHUB_TOKEN:
                logger.info(f"Using system GitHub token for {email}")
                return settings.GITHUB_TOKEN

            raise NoValidPATFoundError(
                f"No GitHub PAT available for user {email} and no system default configured"
            )

        else:
            raise ValueError(f"Unknown platform: {platform}")

    async def get_working_pat(self, email: str, platform: str = "cloudbees") -> str:
        """Get a working PAT for the user, trying fallbacks if needed.

        This is an alias for get_pat for backward compatibility.
        """
        return await self.get_pat(email, platform)

    async def get_fallback_pats(
        self, email: str, platform: str = "cloudbees"
    ) -> list[str]:
        """Get all valid PATs for a user, newest first, with system fallback.

        Used for fallback logic when a PAT fails.
        For GitHub, includes system-wide GitHub PAT as final fallback.
        """
        from .config import settings

        email = email.lower().strip()
        pats = await self.db.get_user_pats(email, platform)

        valid_pats = []

        # First, try user's custom PATs
        for pat_record in pats:
            try:
                decrypted_pat = self.pat_manager.decrypt(pat_record["encrypted_pat"])
                valid_pats.append(decrypted_pat)
            except Exception as e:
                logger.warning(f"Failed to decrypt PAT for {email}: {e}")
                # Mark this PAT as inactive
                await self.db.execute(
                    "UPDATE user_pats SET is_active = false WHERE id = ?",
                    (pat_record["id"],),
                )

        # For GitHub, add system-wide GitHub PAT as fallback
        if platform == "github" and settings.GITHUB_TOKEN:
            valid_pats.append(settings.GITHUB_TOKEN)
            logger.info(f"Added system GitHub PAT as fallback for {email}")

        if not valid_pats:
            raise NoValidPATFoundError(
                f"No valid PATs found for user {email} on platform {platform}"
            )

        return valid_pats

    async def get_pat_by_token(self, email: str, token: str, platform: str = "cloudbees") -> str:
        """Get PAT using a token (database ID).

        Args:
            email: User's email (for verification)
            token: The token (PAT database ID)
            platform: Platform ('cloudbees' or 'github')

        Returns:
            PAT string to use

        Raises:
            NoValidPATFoundError: If token is invalid or doesn't belong to user
        """
        email = email.lower().strip()

        try:
            pat_id = int(token)
        except ValueError:
            raise NoValidPATFoundError(f"Invalid token format for user {email}") from None

        # Get PAT by ID and verify it belongs to the user
        pat_record = await self.db.get_pat_by_id(pat_id)

        if not pat_record:
            raise NoValidPATFoundError(f"Token not found for user {email}")

        # Verify the PAT belongs to the correct user and platform
        if pat_record["email"] != email or pat_record["platform"] != platform:
            raise NoValidPATFoundError(f"Token doesn't belong to user {email} on platform {platform}")

        # Update last_used timestamp
        await self.db.update_pat_last_used(pat_id)

        # Decrypt and return the PAT
        return self.pat_manager.decrypt(pat_record["encrypted_pat"])

    async def refresh_user_activity(self, email: str) -> None:
        """Update user's last_active timestamp.

        Args:
            email: User's email address
        """
        email = email.lower().strip()
        await self.db.execute(
            "UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE email = ?", (email,)
        )


# Global auth service instance
_auth_service: AuthService | None = None


def get_auth_service() -> AuthService:
    """Get the global authentication service instance."""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service
