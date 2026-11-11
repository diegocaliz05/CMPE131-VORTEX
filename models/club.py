from dataclasses import dataclass
from typing import Optional

from .user import Role


@dataclass
class Club:
    """The clubs row, plus the roster/event methods SFDS 5.2 misplaced on 'Event'.
    Methods take the DataStorage so the record itself stays plain data."""
    club_name: str
    description: str = ""
    club_id: Optional[int] = None

    @classmethod
    def from_row(cls, row):
        return cls(club_id=row["club_id"], club_name=row["club_name"],
                   description=row["description"] or "")

    def add_member(self, storage, user_id, role=Role.MEMBER):
        return storage.add_membership(user_id, self.club_id, role)

    def remove_member(self, storage, user_id):
        return storage.remove_membership(user_id, self.club_id)

    def get_events(self, storage, statuses=None):
        return storage.events_for_club(self.club_id, statuses)
