from .authentication import Authentication, LoginResult
from .calendar_display import CalendarDisplay, CalendarView
from .conflict_detection import ConflictCheck, ConflictDetection
from .data_storage import DataStorage
from .event_management import EventManagement, EventValidator
from .notifications import Notifications
from .results import Result
from .search import NO_EVENTS, Search


class Services:
    """Composition root: wires the seven components around one DataStorage."""

    def __init__(self, storage, min_password_length=8):
        self.storage = storage
        self.authentication = Authentication(storage, min_password_length)
        self.conflicts = ConflictDetection(storage)
        self.notifications = Notifications(storage)
        self.events = EventManagement(storage, self.conflicts, self.notifications)
        self.calendar = CalendarDisplay(storage)
        self.search = Search(storage)


__all__ = ["Authentication", "LoginResult", "CalendarDisplay", "CalendarView", "ConflictCheck",
           "ConflictDetection", "DataStorage", "EventManagement", "EventValidator", "Notifications",
           "Result", "Search", "Services", "NO_EVENTS"]
