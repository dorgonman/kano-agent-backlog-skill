"""Git VCS adapter."""

import subprocess
from pathlib import Path
from .base import VcsAdapter, VcsMeta


class GitAdapter:
    """Git VCS adapter."""
    
    def detect(self, repo_root: Path) -> bool:
        """Check if Git is present."""
        return (repo_root / ".git").exists()
    
    def get_metadata(self, repo_root: Path) -> VcsMeta:
        """Get Git metadata."""
        try:
            # Get revision (commit hash)
            revision = subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=repo_root,
                stderr=subprocess.DEVNULL,
                text=True
            ).strip()
            
            # Get ref (branch or HEAD)
            try:
                ref = subprocess.check_output(
                    ["git", "symbolic-ref", "--short", "HEAD"],
                    cwd=repo_root,
                    stderr=subprocess.DEVNULL,
                    text=True
                ).strip()
            except subprocess.CalledProcessError:
                ref = "HEAD"  # detached
            
            # Get label (describe)
            label = None
            try:
                label = subprocess.check_output(
                    ["git", "describe", "--tags", "--always"],
                    cwd=repo_root,
                    stderr=subprocess.DEVNULL,
                    text=True
                ).strip()
            except subprocess.CalledProcessError:
                pass
            
            # Check if dirty
            try:
                subprocess.check_output(
                    ["git", "diff-index", "--quiet", "HEAD", "--"],
                    cwd=repo_root,
                    stderr=subprocess.DEVNULL
                )
                dirty = "false"
            except subprocess.CalledProcessError:
                dirty = "true"
            
            return VcsMeta(
                provider="git",
                revision=revision,
                ref=ref,
                label=label,
                dirty=dirty
            )
        except Exception:
            return VcsMeta(
                provider="git",
                revision="unknown",
                ref="unknown",
                dirty="unknown"
            )