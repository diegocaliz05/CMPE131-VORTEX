from datetime import datetime

from .results import INVALID, Result

NO_EVENTS = "No events found"


class Search:
    """Module 5. Filters: keyword, club, date, location. Visibility follows the caller's role.
    Event type is NOT supported yet: the events table has no type column (SFDS gap)."""

    def __init__(self, storage):
        self._storage = storage

    def search(self, access, keyword=None, club_id=None, date=None, location=None) -> Result:
        date = (date or "").strip() or None
        if date:
            try:
                datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                return Result.fail(INVALID, "Use the date format YYYY-MM-DD.", errors={"date": "use format YYYY-MM-DD"})
        events = self._storage.search_events(
            keyword=(keyword or "").strip() or None, club_id=club_id or None, event_date=date,
            location=(location or "").strip() or None, manage_club_ids=access.authorized_club_ids)
        return Result.success("" if events else NO_EVENTS, events=events)
