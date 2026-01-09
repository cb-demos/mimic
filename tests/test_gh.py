"""Tests for GitHub API client."""

from unittest.mock import AsyncMock, patch

import pytest

from mimic.gh import GitHubClient, parse_github_url


class TestParseGitHubUrl:
    """Tests for parse_github_url function."""

    def test_https_url(self):
        """Test parsing HTTPS GitHub URL."""
        result = parse_github_url("https://github.com/owner/repo")
        assert result == ("owner", "repo")

    def test_https_url_with_git_extension(self):
        """Test parsing HTTPS GitHub URL with .git extension."""
        result = parse_github_url("https://github.com/owner/repo.git")
        assert result == ("owner", "repo")

    def test_https_url_with_trailing_slash(self):
        """Test parsing HTTPS GitHub URL with trailing slash."""
        result = parse_github_url("https://github.com/owner/repo/")
        assert result == ("owner", "repo")

    def test_ssh_url(self):
        """Test parsing SSH GitHub URL."""
        result = parse_github_url("git@github.com:owner/repo.git")
        assert result == ("owner", "repo")

    def test_ssh_url_without_git_extension(self):
        """Test parsing SSH GitHub URL without .git extension."""
        result = parse_github_url("git@github.com:owner/repo")
        assert result == ("owner", "repo")

    def test_ssh_protocol_url(self):
        """Test parsing SSH protocol GitHub URL."""
        result = parse_github_url("ssh://git@github.com/owner/repo.git")
        assert result == ("owner", "repo")

    def test_ssh_protocol_url_with_port(self):
        """Test parsing SSH protocol GitHub URL with port."""
        result = parse_github_url("ssh://git@github.com:22/owner/repo.git")
        assert result == ("owner", "repo")

    def test_non_github_url(self):
        """Test parsing non-GitHub URL returns None."""
        result = parse_github_url("https://gitlab.com/owner/repo")
        assert result is None

    def test_invalid_url(self):
        """Test parsing invalid URL returns None."""
        result = parse_github_url("not a url")
        assert result is None


class TestGitHubClientBranches:
    """Tests for GitHubClient branch-related methods."""

    @pytest.mark.asyncio
    async def test_list_branches_success(self):
        """Test listing branches successfully."""
        client = GitHubClient("test_token")

        mock_response = AsyncMock()
        mock_response.status_code = 200
        # json() is a regular method that returns data, not async
        mock_response.json = lambda: [
            {
                "name": "main",
                "commit": {"sha": "abc123"},
                "protected": False,
            },
            {
                "name": "develop",
                "commit": {"sha": "def456"},
                "protected": True,
            },
        ]

        with patch.object(client, "_request", return_value=mock_response):
            branches = await client.list_branches("owner", "repo")

        assert len(branches) == 2
        assert branches[0]["name"] == "main"
        assert branches[1]["name"] == "develop"
        assert branches[1]["protected"] is True

    @pytest.mark.asyncio
    async def test_list_branches_404(self):
        """Test listing branches for non-existent repo returns empty list."""
        client = GitHubClient("test_token")

        mock_response = AsyncMock()
        mock_response.status_code = 404

        with patch.object(client, "_request", return_value=mock_response):
            branches = await client.list_branches("owner", "repo")

        assert branches == []

    @pytest.mark.asyncio
    async def test_list_branches_exception(self):
        """Test listing branches with exception returns empty list."""
        client = GitHubClient("test_token")

        with patch.object(client, "_request", side_effect=Exception("Network error")):
            branches = await client.list_branches("owner", "repo")

        assert branches == []


class TestGitHubClientPullRequests:
    """Tests for GitHubClient pull request methods."""

    @pytest.mark.asyncio
    async def test_list_pull_requests_success(self):
        """Test listing pull requests successfully."""
        client = GitHubClient("test_token")

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = lambda: [
            {
                "number": 123,
                "title": "Add feature X",
                "head": {"ref": "feature-x", "sha": "abc123"},
                "user": {"login": "contributor"},
                "state": "open",
            },
        ]

        with patch.object(client, "_request", return_value=mock_response):
            prs = await client.list_pull_requests("owner", "repo")

        assert len(prs) == 1
        assert prs[0]["number"] == 123
        assert prs[0]["title"] == "Add feature X"
        assert prs[0]["user"]["login"] == "contributor"

    @pytest.mark.asyncio
    async def test_list_pull_requests_with_state(self):
        """Test listing pull requests with specific state."""
        client = GitHubClient("test_token")

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = lambda: []

        with patch.object(
            client, "_request", return_value=mock_response
        ) as mock_request:
            await client.list_pull_requests("owner", "repo", state="closed")

        # Verify state parameter was passed
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[1]["params"]["state"] == "closed"

    @pytest.mark.asyncio
    async def test_list_pull_requests_404(self):
        """Test listing PRs for non-existent repo returns empty list."""
        client = GitHubClient("test_token")

        mock_response = AsyncMock()
        mock_response.status_code = 404

        with patch.object(client, "_request", return_value=mock_response):
            prs = await client.list_pull_requests("owner", "repo")

        assert prs == []

    @pytest.mark.asyncio
    async def test_list_pull_requests_exception(self):
        """Test listing PRs with exception returns empty list."""
        client = GitHubClient("test_token")

        with patch.object(client, "_request", side_effect=Exception("Network error")):
            prs = await client.list_pull_requests("owner", "repo")

        assert prs == []


class TestGitHubClientDefaultBranch:
    """Tests for GitHubClient default branch method."""

    @pytest.mark.asyncio
    async def test_get_default_branch_success(self):
        """Test getting default branch successfully."""
        client = GitHubClient("test_token")

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = lambda: {
            "name": "my-repo",
            "default_branch": "main",
        }

        with patch.object(client, "_request", return_value=mock_response):
            default_branch = await client.get_default_branch("owner", "repo")

        assert default_branch == "main"

    @pytest.mark.asyncio
    async def test_get_default_branch_master(self):
        """Test getting default branch when it's master."""
        client = GitHubClient("test_token")

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = lambda: {
            "name": "legacy-repo",
            "default_branch": "master",
        }

        with patch.object(client, "_request", return_value=mock_response):
            default_branch = await client.get_default_branch("owner", "repo")

        assert default_branch == "master"

    @pytest.mark.asyncio
    async def test_get_default_branch_404(self):
        """Test getting default branch for non-existent repo returns None."""
        client = GitHubClient("test_token")

        mock_response = AsyncMock()
        mock_response.status_code = 404

        with patch.object(client, "_request", return_value=mock_response):
            default_branch = await client.get_default_branch("owner", "repo")

        assert default_branch is None

    @pytest.mark.asyncio
    async def test_get_default_branch_exception(self):
        """Test getting default branch with exception returns None."""
        client = GitHubClient("test_token")

        with patch.object(client, "_request", side_effect=Exception("Network error")):
            default_branch = await client.get_default_branch("owner", "repo")

        assert default_branch is None
