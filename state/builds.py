"""
Thread-safe storage for pending builds.
"""

from bot.models.pending import PendingBuild


class BuildsStore:
    """Storage for pending GitHub Actions builds."""
    
    def __init__(self):
        self._builds: dict[str, PendingBuild] = {}
    
    def add(self, sha: str, build: PendingBuild) -> None:
        """Add a pending build."""
        self._builds[sha] = build
    
    def pop(self, sha: str) -> PendingBuild | None:
        """Remove and return a pending build by SHA."""
        return self._builds.pop(sha, None)
    
    def get(self, sha: str) -> PendingBuild | None:
        """Get a pending build by SHA without removing."""
        return self._builds.get(sha)
    
    def get_all_shas(self) -> list[str]:
        """Get all pending build SHAs."""
        return list(self._builds.keys())
    
    def __contains__(self, sha: str) -> bool:
        return sha in self._builds


# Singleton instance
pending_builds = BuildsStore()
