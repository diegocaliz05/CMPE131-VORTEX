from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

OK, DENIED, INVALID, CONFLICT, DUPLICATE = "ok", "denied", "invalid", "conflict", "duplicate"
NOT_FOUND, BAD_STATE, CONFIRM_REQUIRED, STORAGE_ERROR = "not_found", "bad_state", "confirm_required", "storage_error"


@dataclass
class Result:
    """Uniform return value for every write/read contract. Routes branch on .code."""
    ok: bool
    code: str = OK
    message: str = ""
    event: Optional[Any] = None
    events: List[Any] = field(default_factory=list)
    user: Optional[Any] = None
    conflicts: List[Any] = field(default_factory=list)
    errors: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def success(cls, message="", **kw):
        return cls(True, OK, message, **kw)

    @classmethod
    def fail(cls, code, message="", **kw):
        return cls(False, code, message, **kw)

    @classmethod
    def denied(cls):
        return cls.fail(DENIED, "Only officers of this club can do that.")

    @classmethod
    def not_found(cls, what="Event"):
        return cls.fail(NOT_FOUND, f"{what} not found.")
