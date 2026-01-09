"""Kano Backlog Core - Transport-agnostic backlog domain library."""

__version__ = "0.1.0"

from .config import BacklogContext, ConfigLoader
from .canonical import BacklogItem, CanonicalStore, ItemType, ItemState
from .derived import DerivedStore, InMemoryDerivedStore
from .refs import RefParser, RefResolver
from .state import StateMachine, ReadyValidator, StateAction
from .audit import AuditLog, WorklogEntry
from .errors import (
    BacklogError,
    ConfigError,
    ItemNotFoundError,
    ParseError,
    ValidationError,
    WriteError,
)

__all__ = [
    # Version
    "__version__",
    # Config
    "BacklogContext",
    "ConfigLoader",
    # Canonical
    "BacklogItem",
    "CanonicalStore",
    "ItemType",
    "ItemState",
    # Derived
    "DerivedStore",
    "InMemoryDerivedStore",
    # Refs
    "RefParser",
    "RefResolver",
    # State
    "StateMachine",
    "ReadyValidator",
    "StateAction",
    # Audit
    "AuditLog",
    "WorklogEntry",
    # Errors
    "BacklogError",
    "ConfigError",
    "ItemNotFoundError",
    "ParseError",
    "ValidationError",
    "WriteError",
]
