from typing import Any

import httpx

from .config import settings


class GitHubClient:
    """GitHub API client."""

    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def _request(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        """Make an authenticated request to the GitHub API."""
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method,
                url=f"{self.base_url}{endpoint}",
                headers=self.headers,
                **kwargs,
            )
            return response

    async def repo_exists(self, owner: str, repo: str) -> bool:
        """Check if a repository exists."""
        response = await self._request("GET", f"/repos/{owner}/{repo}")
        return response.status_code == 200

    async def create_repo_from_template(
        self,
        template_owner: str,
        template_repo: str,
        owner: str,
        name: str,
        description: str | None = None,
        private: bool = False,
    ) -> dict[str, Any]:
        """
        Create a new repository from a template.

        Args:
            template_owner: Owner of the template repository
            template_repo: Name of the template repository
            owner: Owner for the new repository (org or user)
            name: Name for the new repository
            description: Optional description for the new repository
            private: Whether the new repository should be private

        Returns:
            The created repository data
        """
        data = {"owner": owner, "name": name, "private": private}
        if description:
            data["description"] = description

        response = await self._request(
            "POST", f"/repos/{template_owner}/{template_repo}/generate", json=data
        )
        response.raise_for_status()
        return response.json()

    async def get_file_in_repo(
        self, owner: str, repo: str, path: str
    ) -> dict[str, Any] | None:
        """Get file contents and metadata from repo."""
        import base64

        response = await self._request("GET", f"/repos/{owner}/{repo}/contents/{path}")
        if response.status_code == 200:
            data = response.json()
            if "content" in data:
                # Content is base64 encoded, decode it
                content_bytes = base64.b64decode(data["content"])
                data["decoded_content"] = content_bytes.decode("utf-8")
            return data
        return None

    async def get_repo_public_key(self, owner: str, repo: str) -> dict[str, Any] | None:
        """
        Get the repository's public key for encrypting secrets.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            Public key data including key_id and key
        """
        response = await self._request(
            "GET", f"/repos/{owner}/{repo}/actions/secrets/public-key"
        )
        if response.status_code == 200:
            return response.json()
        return None

    async def create_or_update_secret(
        self, owner: str, repo: str, secret_name: str, secret_value: str
    ) -> bool:
        """
        Create or update a GitHub Actions secret.

        Args:
            owner: Repository owner
            repo: Repository name
            secret_name: Name of the secret
            secret_value: Value of the secret (will be encrypted)

        Returns:
            True if successful, False otherwise
        """
        import base64

        from nacl import encoding, public

        # Get the repository's public key
        public_key_data = await self.get_repo_public_key(owner, repo)
        if not public_key_data:
            print(f"Failed to get public key for {owner}/{repo}")
            return False

        # Encrypt the secret value
        public_key = public.PublicKey(
            public_key_data["key"].encode("utf-8"), encoding.Base64Encoder
        )
        sealed_box = public.SealedBox(public_key)
        encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
        encrypted_value = base64.b64encode(encrypted).decode("utf-8")

        # Create or update the secret
        data = {"encrypted_value": encrypted_value, "key_id": public_key_data["key_id"]}

        response = await self._request(
            "PUT", f"/repos/{owner}/{repo}/actions/secrets/{secret_name}", json=data
        )

        if response.status_code in [201, 204]:
            return True
        else:
            print(
                f"Error creating/updating secret: {response.status_code} - {response.text}"
            )
            return False

    async def replace_file(
        self,
        owner: str,
        repo: str,
        path: str,
        content: str,
        message: str,
        sha: str,
        branch: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Replace file contents in a repository.

        Args:
            owner: Repository owner
            repo: Repository name
            path: File path in the repository
            content: New file content (will be base64 encoded)
            message: Commit message
            sha: SHA of the file being replaced (required for updates)
            branch: Branch to update (optional, defaults to default branch)

        Returns:
            Commit data if successful, None otherwise
        """
        import base64

        # Encode content to base64
        content_bytes = content.encode("utf-8")
        content_base64 = base64.b64encode(content_bytes).decode("ascii")

        data = {"message": message, "content": content_base64, "sha": sha}

        if branch:
            data["branch"] = branch

        response = await self._request(
            "PUT", f"/repos/{owner}/{repo}/contents/{path}", json=data
        )

        if response.status_code in [200, 201]:
            return response.json()
        else:
            print(f"Error updating file: {response.status_code} - {response.text}")
            return None

    async def create_file(
        self,
        owner: str,
        repo: str,
        path: str,
        content: str,
        message: str,
        branch: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Create a new file in a repository.

        Args:
            owner: Repository owner
            repo: Repository name
            path: File path in the repository
            content: File content (will be base64 encoded)
            message: Commit message
            branch: Branch to create the file on (defaults to default branch)

        Returns:
            API response data or None if failed
        """
        import base64

        # Base64 encode the content
        encoded_content = base64.b64encode(content.encode()).decode()

        data = {
            "message": message,
            "content": encoded_content,
        }

        if branch:
            data["branch"] = branch

        response = await self._request(
            "PUT", f"/repos/{owner}/{repo}/contents/{path}", json=data
        )

        return response.json() if response.status_code in (200, 201) else None

    async def delete_file(
        self,
        owner: str,
        repo: str,
        path: str,
        message: str,
        sha: str,
        branch: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Delete a file from a repository.

        Args:
            owner: Repository owner
            repo: Repository name
            path: File path in the repository
            message: Commit message
            sha: SHA of the file being deleted (required)
            branch: Branch to delete the file from (defaults to default branch)

        Returns:
            API response data or None if failed
        """
        data = {
            "message": message,
            "sha": sha,
        }

        if branch:
            data["branch"] = branch

        response = await self._request(
            "DELETE", f"/repos/{owner}/{repo}/contents/{path}", json=data
        )

        return response.json() if response.status_code == 200 else None

    async def check_user_collaboration(
        self, owner: str, repo: str, username: str
    ) -> bool:
        """Check if a user is already a collaborator on a repository."""
        response = await self._request(
            "GET", f"/repos/{owner}/{repo}/collaborators/{username}"
        )
        return response.status_code == 204

    async def invite_collaborator(
        self, owner: str, repo: str, username: str, permission: str = "admin"
    ) -> bool:
        """
        Invite a user as a collaborator to a repository.

        Args:
            owner: Repository owner
            repo: Repository name
            username: GitHub username to invite
            permission: Permission level (admin, maintain, push, triage, pull)

        Returns:
            True if invitation was successful, False otherwise
        """
        data = {"permission": permission}
        response = await self._request(
            "PUT", f"/repos/{owner}/{repo}/collaborators/{username}", json=data
        )

        if response.status_code in [201, 204]:
            return True
        else:
            print(
                f"Error inviting collaborator: {response.status_code} - {response.text}"
            )
            return False


github = GitHubClient(settings.GITHUB_TOKEN)
