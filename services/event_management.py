import logging
from datetime import datetime

from exceptions import DuplicateRecordError, StorageError
from models import Event, EventStatus
from .results import (BAD_STATE, CONFIRM_REQUIRED, CONFLICT, DUPLICATE, INVALID, STORAGE_ERROR, Result)

log = logging.getLogger("vortex.events")
_LIMITS = {"event_name": 120, "description": 2000, "location": 200}
REQUIRED = ("event_name", "event_date", "start_time", "end_time", "location")


class EventValidator:
    """Normalises event input and reports every problem at once: (cleaned, errors)."""

    def validate(self, data):
        cleaned = {k: str(data.get(k) or "").strip() for k in
                   ("event_name", "description", "event_date", "start_time", "end_time", "location")}
        errors = {f: "required" for f in REQUIRED if not cleaned[f]}
        for field_name, limit in _LIMITS.items():
            if len(cleaned[field_name]) > limit:
                errors[field_name] = f"must be at most {limit} characters"
        if "event_date" not in errors:
            try:
                cleaned["event_date"] = datetime.strptime(cleaned["event_date"], "%Y-%m-%d").strftime("%Y-%m-%d")
            except ValueError:
                errors["event_date"] = "use format YYYY-MM-DD"
        for f in ("start_time", "end_time"):
            if f not in errors:
                try:
                    cleaned[f] = datetime.strptime(cleaned[f], "%H:%M").strftime("%H:%M")
                except ValueError:
                    errors[f] = "use format HH:MM"
        if not errors and cleaned["end_time"] <= cleaned["start_time"]:
            errors["end_time"] = "must be after the start time"
        return cleaned, errors


class EventManagement:
    """Module 2. Every write needs an officer Membership for the event's club_id; a member
    (or an officer of another club) gets a denial Result. Writes return Result, never raise."""

    def __init__(self, storage, conflicts, notifications, validator=None):
        self._storage, self._conflicts, self._notifications = storage, conflicts, notifications
        self._validator = validator or EventValidator()

    def _run(self, work):
        """Run `work` in one transaction; returns a failure Result or None on success."""
        try:
            with self._storage.transaction():
                work()
        except DuplicateRecordError:
            return Result.fail(DUPLICATE, "That event already exists.")
        except StorageError:
            log.exception("storage failure")
            return Result.fail(STORAGE_ERROR, "The event could not be saved. Please try again.")
        return None

    def get_event(self, access, event_id) -> Result:
        """Tentative/cancelled events are visible only to officers of that club."""
        event = self._storage.get_event(event_id)
        if event is None or (event.status != EventStatus.CONFIRMED and not access.is_officer_of(event.club_id)):
            return Result.not_found()
        return Result.success(event=event)

    def create_event(self, access, club_id, data, acknowledge_conflicts=False) -> Result:
        if not access.is_officer_of(club_id):
            return Result.denied()
        club = self._storage.get_club(club_id)
        if club is None:
            return Result.not_found("Club")
        cleaned, errors = self._validator.validate(data)
        if errors:
            return Result.fail(INVALID, "Fix the highlighted fields.", errors=errors)
        event = Event(club_id=club_id, club_name=club.club_name, status=EventStatus.TENTATIVE, **cleaned)
        if self._storage.find_duplicate(event):
            return Result.fail(DUPLICATE, "That event already exists.")
        check = self._conflicts.check(event.event_date, event.start_time, event.end_time, event.location)
        if check.has_conflict and not acknowledge_conflicts:
            return Result.fail(CONFLICT, "This overlaps another event. Save anyway to keep it tentative.",
                               conflicts=check.conflicts)
        failure = self._run(lambda: self._storage.add_event(event))
        if failure:
            return failure
        log.info("event created id=%s club=%s", event.event_id, club_id)
        return Result.success("Event saved as tentative.", event=event)

    def edit_event(self, access, event_id, data, acknowledge_conflicts=False) -> Result:
        found = self._storage.get_event(event_id)
        if found is None:
            return Result.not_found()
        if not access.is_officer_of(found.club_id):
            return Result.denied()
        if found.status == EventStatus.CANCELLED:
            return Result.fail(BAD_STATE, "Cancelled events cannot be edited.")
        cleaned, errors = self._validator.validate(data)
        if errors:
            return Result.fail(INVALID, "Fix the highlighted fields.", errors=errors)
        updated = Event(club_id=found.club_id, club_name=found.club_name, status=found.status,
                        event_id=found.event_id, **cleaned)
        if self._storage.find_duplicate(updated, exclude_event_id=found.event_id):
            return Result.fail(DUPLICATE, "That event already exists.")
        public = updated.status == EventStatus.CONFIRMED
        check = self._conflicts.check(updated.event_date, updated.start_time, updated.end_time,
                                      updated.location, exclude_event_id=found.event_id,
                                      statuses=[EventStatus.CONFIRMED] if public else None)
        if check.has_conflict and (public or not acknowledge_conflicts):
            return Result.fail(CONFLICT, "This change overlaps another event.", conflicts=check.conflicts)

        def work():
            self._storage.update_event(updated)
            if public:
                self._notifications.create_notification(updated, "updated")
        failure = self._run(work)
        return failure or Result.success("Event updated.", event=updated)

    def confirm_event(self, access, event_id) -> Result:
        event = self._storage.get_event(event_id)
        if event is None:
            return Result.not_found()
        if not access.is_officer_of(event.club_id):
            return Result.denied()
        if not event.can_transition_to(EventStatus.CONFIRMED):
            return Result.fail(BAD_STATE, "Only tentative events can be confirmed.")
        _, errors = self._validator.validate(event.to_dict())
        if errors:
            return Result.fail(INVALID, "Complete the event before confirming.", errors=errors)
        # Only a CONFIRMED event can block confirmation, otherwise two tentative
        # events in the same slot could never be confirmed.
        check = self._conflicts.check(event.event_date, event.start_time, event.end_time, event.location,
                                      exclude_event_id=event.event_id, statuses=[EventStatus.CONFIRMED])
        if check.has_conflict:
            return Result.fail(CONFLICT, "Resolve the conflict before confirming.", conflicts=check.conflicts)
        event.status = EventStatus.CONFIRMED

        def work():
            self._storage.set_event_status(event.event_id, event.status)
            self._notifications.create_notification(event, "confirmed")
        failure = self._run(work)
        return failure or Result.success("Event confirmed.", event=event)

    def cancel_event(self, access, event_id, confirmed=False) -> Result:
        event = self._storage.get_event(event_id)
        if event is None:
            return Result.not_found()
        if not access.is_officer_of(event.club_id):
            return Result.denied()
        if not event.can_transition_to(EventStatus.CANCELLED):
            return Result.fail(BAD_STATE, "This event is already cancelled.")
        if not confirmed:
            return Result.fail(CONFIRM_REQUIRED, "Confirm that you want to cancel this event.", event=event)
        was_public = event.status == EventStatus.CONFIRMED
        event.status = EventStatus.CANCELLED

        def work():
            self._storage.set_event_status(event.event_id, event.status)
            if was_public:  # members never saw a tentative event
                self._notifications.create_notification(event, "cancelled")
        failure = self._run(work)
        return failure or Result.success("Event cancelled.", event=event)
