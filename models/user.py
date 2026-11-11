from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class Role(str, Enum):
    MEMBER = "member"
    OFFICER = "officer"


@dataclass
class User:
    """The users row. No role and no club: those live on Membership."""
    name: str
    email: str
    password_hash: str = field(default="", repr=False)   # never log or render this
    user_id: Optional[int] = None

    @classmethod
    def from_row(cls, row):
        return cls(user_id=row["user_id"], name=row["name"], email=row["email"],
                   password_hash=row["password_hash"])


@dataclass
class Membership:
    """The memberships row: one user's role in one club."""
    user_id: int
    club_id: int
    role: Role = Role.MEMBER
    membership_id: Optional[int] = None

    @classmethod
    def from_row(cls, row):
        return cls(membership_id=row["membership_id"], user_id=row["user_id"],
                   club_id=row["club_id"], role=Role(row["role"]))


@dataclass
class Access:
    """A user plus their memberships: what services check authorization against.
    An 'officer' is not a subclass; authorized_clubs is a filtered view of the memberships."""
    user: User
    memberships: List[Membership] = field(default_factory=list)

    @property
    def authorized_clubs(self) -> List[Membership]:
        return [m for m in self.memberships if m.role == Role.OFFICER]

    @property
    def authorized_club_ids(self):
        return frozenset(m.club_id for m in self.authorized_clubs)

    @property
    def is_officer(self) -> bool:
        return bool(self.authorized_clubs)

    def is_officer_of(self, club_id) -> bool:
        return club_id in self.authorized_club_ids

    @property
    def user_id(self):
        return self.user.user_id

    @property
    def name(self):
        return self.user.name

    @property
    def role_label(self):
        return "Officer" if self.is_officer else "Member"
