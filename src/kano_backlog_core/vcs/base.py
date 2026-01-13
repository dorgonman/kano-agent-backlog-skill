"""VCS abstraction base types."""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol


@dataclass
class VcsMeta:
    """VCS metadata for reproducible builds."""
    provider: str  # git, p4, svn, none, unknown
    revision: str  # commit hash, changelist, etc. or "unknown"
    ref: str  # branch, stream, etc. or "unknown"
    label: Optional[str] = None  # tag, describe, etc.
    dirty: str = "unknown"  # "true", "false", "unknown"


class VcsAdapter(Protocol):
    """VCS adapter protocol."""
    
    def detect(self, repo_root: Path) -> bool:
        """Check if this VCS is present."""
        ...
    
    def get_metadata(self, repo_root: Path) -> VcsMeta:
        """Get VCS metadata."""
        ...