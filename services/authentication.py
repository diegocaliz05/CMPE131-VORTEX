import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from werkzeug.security import check_password_hash, generate_password_hash

from exceptions import DuplicateRecordError, StorageError
from models import Access, Membership, User
from .results import INVALID, DUPLICATE, STORAGE_ERROR, Result

log = logging.getLogger("vortex.authentication")  # never log passwords or hashes
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class LoginResult:
    ok: bool
    user: Optional[User] = None
    memberships: list = field(default_factory=list)
    session: dict = field(default_factory=dict)
    error: str = ""

    @property
    def access(self):
        return Access(self.user, self.memberships) if self.ok else None


class Authentication:
    """Module 1 (SFDS 4.1, FR1)."""

    def __init__(self, storage, min_password_length=8):
        self._storage, self._min_len = storage, min_password_length

    def register(self, name, email, password) -> Result:
        name, email = (name or "").strip(), (email or "").strip().lower()
        errors = {}
        if not name:
            errors["name"] = "required"
        if not _EMAIL.match(email):
            errors["email"] = "enter a valid email"
        if len(password or "") < self._min_len:
            errors["password"] = f"must be at least {self._min_len} characters"
        if errors:
            return Result.fail(INVALID, "Check the highlighted fields.", errors=errors)
        try:
            with self._storage.transaction():
                user = self._storage.add_user(User(name, email, generate_password_hash(password)))
        except DuplicateRecordError:
            return Result.fail(DUPLICATE, "That email is already registered.", errors={"email": "already registered"})
        except StorageError:
            return Result.fail(STORAGE_ERROR, "Could not create the account.")
        return Result.success("Account created.", user=user)

    def login(self, email, password) -> LoginResult:
        """Returns the user, their memberships and a session dict, or a login error.
        Unknown email and wrong password produce the same message."""
        user = self._storage.get_user_by_email(email or "")
        if user is None or not check_password_hash(user.password_hash, password or ""):
            log.info("failed login attempt")
            return LoginResult(False, error="Invalid email or password.")
        log.info("successful login user_id=%s", user.user_id)
        memberships = self._storage.get_memberships(user.user_id)
        return LoginResult(True, user, memberships, {"user_id": user.user_id})

    def logout(self) -> dict:
        """Returns the empty session the caller should store."""
        return {}

    def load_access(self, user_id) -> Optional[Access]:
        """Rebuild user + memberships from a session's user_id (None if unknown)."""
        user = self._storage.get_user(user_id) if user_id else None
        return Access(user, self._storage.get_memberships(user.user_id)) if user else None
