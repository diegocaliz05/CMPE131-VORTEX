from dataclasses import asdict, dataclass
from enum import Enum
from typing import Optional


class EventStatus(str, Enum):
    TENTATIVE = "tentative"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


_TRANSITIONS = {
    EventStatus.TENTATIVE: {EventStatus.CONFIRMED, EventStatus.CANCELLED},
    EventStatus.CONFIRMED: {EventStatus.CANCELLED},
    EventStatus.CANCELLED: set(),
}


@dataclass
class Event:
    """The events row, field names identical to schema.sql.
    event_date is YYYY-MM-DD and times are zero-padded HH:MM, so string order == time order."""
    club_id: int
    event_name: str
    event_date: str
    start_time: str
    end_time: str
    location: str = ""
    description: str = ""
    status: EventStatus = EventStatus.TENTATIVE
    event_id: Optional[int] = None
    club_name: str = ""          # joined for display only, not a column

    @classmethod
    def from_row(cls, row):
        keys = row.keys()
        return cls(event_id=row["event_id"], club_id=row["club_id"], event_name=row["event_name"],
                   description=row["description"] or "", event_date=row["event_date"],
                   start_time=row["start_time"], end_time=row["end_time"],
                   location=row["location"] or "", status=EventStatus(row["status"]),
                   club_name=row["club_name"] if "club_name" in keys else "")

    def can_transition_to(self, status: EventStatus) -> bool:
        return status in _TRANSITIONS[self.status]

    def overlaps(self, event_date, start_time, end_time) -> bool:
        """Same day, intersecting times. Back-to-back events do not overlap."""
        return (self.event_date == event_date and self.start_time < end_time
                and start_time < self.end_time)

    def to_dict(self):
        data = asdict(self)
        data["status"] = self.status.value
        return data
