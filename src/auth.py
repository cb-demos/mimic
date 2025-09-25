"""User authentication services for the cleanup system."""

import logging

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

    async def get_working_pat(self, email: str, platform: str = "cloudbees") -> str:
        """Get the most recent PAT for a user. Cleanup logic will handle testing if it works.

        Args:
            email: User's email
            platform: Platform ('cloudbees' or 'github')

        Returns:
            The most recent decrypted PAT

        Raises:
            NoValidPATFoundError: If no PAT is found
        """
        email = email.lower().strip()
        pats = await self.db.get_user_pats(email, platform)

        if not pats:
            raise NoValidPATFoundError(f"No PATs found for user {email} on {platform}")

        # Return the most recent PAT (first in the ordered list)
        most_recent_pat = pats[0]
        return self.pat_manager.decrypt(most_recent_pat["encrypted_pat"])

    async def get_fallback_pats(
        self, email: str, platform: str = "cloudbees"
    ) -> list[str]:
        """Get all PATs for a user in order (newest first) for fallback attempts.

        Args:
            email: User's email
            platform: Platform ('cloudbees' or 'github')

        Returns:
            List of decrypted PATs in order from newest to oldest

        Raises:
            NoValidPATFoundError: If no PATs are found
        """
        email = email.lower().strip()
        pats = await self.db.get_user_pats(email, platform)

        if not pats:
            raise NoValidPATFoundError(f"No PATs found for user {email} on {platform}")

        decrypted_pats = []
        for pat_row in pats:
            try:
                decrypted_pat = self.pat_manager.decrypt(pat_row["encrypted_pat"])
                decrypted_pats.append(decrypted_pat)
            except Exception as e:
                logger.warning(
                    f"Failed to decrypt PAT {pat_row['id']} for {email}: {e}"
                )
                # Mark this PAT as inactive since it can't be decrypted
                await self.db.mark_pat_inactive(pat_row["id"])
                continue

        if not decrypted_pats:
            raise NoValidPATFoundError(
                f"No valid PATs found for user {email} on {platform}"
            )

        return decrypted_pats

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
