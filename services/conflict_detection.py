from dataclasses import dataclass, field

from models import EventStatus


@dataclass
class ConflictCheck:
    conflicts: list = field(default_factory=list)

    @property
    def has_conflict(self) -> bool:
        return bool(self.conflicts)


class ConflictDetection:
    """Module 3 (SFDS 4.2). Read-only: never saves. Two events conflict when they are on the
    same date, their times overlap, and they use the same location."""

    ACTIVE = (EventStatus.TENTATIVE, EventStatus.CONFIRMED)

    def __init__(self, storage):
        self._storage = storage

    def check(self, date, start, end, location, exclude_event_id=None, statuses=None) -> ConflictCheck:
        place = (location or "").strip().casefold()
        if not place:
            return ConflictCheck()
        hits = [e for e in self._storage.find_events(date, statuses or self.ACTIVE)
                if e.event_id != exclude_event_id and e.location.strip().casefold() == place
                and e.overlaps(date, start, end)]
        return ConflictCheck(hits)
