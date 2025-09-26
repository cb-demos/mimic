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
        """Store user tokens securely without verification.

        Args:
            email: User's company email address
            unify_pat: CloudBees Unify PAT
            github_pat: Optional GitHub PAT
            name: Optional display name

        Returns:
            User details dictionary
        """
        # Normalize email to lowercase
        email = email.lower().strip()

        # Store user record
        await self.db.create_user(email, name)

        # Encrypt and store PATs
        encrypted_unify_pat = self.pat_manager.encrypt(unify_pat)
        await self.db.store_pat(email, encrypted_unify_pat, "cloudbees")

        if github_pat:
            encrypted_github_pat = self.pat_manager.encrypt(github_pat)
            await self.db.store_pat(email, encrypted_github_pat, "github")

        logger.info(f"Successfully stored tokens for {email}")

        return {"email": email, "name": name, "has_github_pat": bool(github_pat)}

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
