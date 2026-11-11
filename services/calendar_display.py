from collections import OrderedDict
from dataclasses import dataclass, field


@dataclass
class CalendarView:
    view: str                      # "officer" or "member"
    events: list = field(default_factory=list)
    by_date: dict = field(default_factory=OrderedDict)


class CalendarDisplay:
    """Module 4. Officers get tentative + confirmed events for clubs they officer, plus other
    clubs' confirmed events; members get confirmed events only."""

    def __init__(self, storage):
        self._storage = storage

    def view(self, access) -> CalendarView:
        events = self._storage.search_events(manage_club_ids=access.authorized_club_ids)
        by_date = OrderedDict()
        for e in events:
            by_date.setdefault(e.event_date, []).append(e)
        return CalendarView("officer" if access.is_officer else "member", events, by_date)
