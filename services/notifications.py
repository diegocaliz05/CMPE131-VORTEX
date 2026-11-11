import logging

from models import Notification

log = logging.getLogger("vortex.notifications")


class Notifications:
    """Module 6. One row per affected club member. Failures are logged, never raised,
    so a notification problem cannot lose an event save (SFDS 9.1)."""

    def __init__(self, storage):
        self._storage = storage

    def create_notification(self, event, action) -> int:
        message = (f"{event.club_name or 'Club'}: \"{event.event_name}\" was {action} "
                   f"({event.event_date} {event.start_time}-{event.end_time}).")
        created = 0
        try:
            for user_id in self._storage.member_ids(event.club_id):
                self._storage.add_notification(Notification(user_id, message, event.event_id))
                created += 1
        except Exception:
            log.exception("notification failure for event_id=%s", event.event_id)
        return created

    def list_for(self, user_id):
        return self._storage.get_notifications(user_id)

    def unread_count(self, user_id):
        return self._storage.count_unread(user_id)

    def mark_read(self, notification_id, user_id) -> bool:
        with self._storage.transaction():
            return self._storage.mark_notification_read(notification_id, user_id)
