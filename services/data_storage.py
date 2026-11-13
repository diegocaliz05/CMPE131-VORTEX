import sqlite3
from contextlib import contextmanager

from database import get_db_connection
from exceptions import DuplicateRecordError, StorageError
from models import (Club, Event, EventStatus, Membership, Notification, Role, User)

_EVENT_SELECT = "SELECT e.*, c.club_name FROM events e JOIN clubs c ON c.club_id = e.club_id"


def _like(term):
    return "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


class DataStorage:
    """Module 7. The ONLY class that runs SQL. Other classes pass records in and get
    records out. Write methods never commit; wrap multi-step work in transaction()."""

    def __init__(self, conn=None, db_path=None):
        self.conn = conn or get_db_connection(db_path)

    def close(self):
        self.conn.close()

    @contextmanager
    def transaction(self):
        try:
            yield self
            self.conn.commit()
        except sqlite3.IntegrityError as exc:
            self.conn.rollback()
            raise DuplicateRecordError(str(exc)) from exc
        except sqlite3.Error as exc:
            self.conn.rollback()
            raise StorageError(str(exc)) from exc
        except Exception:
            self.conn.rollback()
            raise

    # ---- users ----
    def add_user(self, user: User) -> User:
        user.email = user.email.strip().lower()
        user.user_id = self.conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (user.name, user.email, user.password_hash)).lastrowid
        return user

    def get_user(self, user_id):
        row = self.conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return User.from_row(row) if row else None

    def get_user_by_email(self, email):
        row = self.conn.execute("SELECT * FROM users WHERE email = ?",
                                ((email or "").strip().lower(),)).fetchone()
        return User.from_row(row) if row else None

    # ---- clubs & memberships ----
    def add_club(self, club: Club) -> Club:
        club.club_id = self.conn.execute(
            "INSERT INTO clubs (club_name, description) VALUES (?, ?)",
            (club.club_name, club.description)).lastrowid
        return club

    def get_club(self, club_id):
        row = self.conn.execute("SELECT * FROM clubs WHERE club_id = ?", (club_id,)).fetchone()
        return Club.from_row(row) if row else None

    def list_clubs(self):
        return [Club.from_row(r) for r in self.conn.execute("SELECT * FROM clubs ORDER BY club_name")]

    def add_membership(self, user_id, club_id, role=Role.MEMBER) -> Membership:
        role = Role(role)
        row = self.conn.execute("SELECT membership_id FROM memberships WHERE user_id = ? AND club_id = ?",
                                (user_id, club_id)).fetchone()
        if row:
            self.conn.execute("UPDATE memberships SET role = ? WHERE membership_id = ?",
                              (role.value, row["membership_id"]))
            return Membership(user_id, club_id, role, row["membership_id"])
        mid = self.conn.execute("INSERT INTO memberships (user_id, club_id, role) VALUES (?, ?, ?)",
                                (user_id, club_id, role.value)).lastrowid
        return Membership(user_id, club_id, role, mid)

    def remove_membership(self, user_id, club_id) -> bool:
        return self.conn.execute("DELETE FROM memberships WHERE user_id = ? AND club_id = ?",
                                 (user_id, club_id)).rowcount > 0

    def get_memberships(self, user_id):
        return [Membership.from_row(r) for r in
                self.conn.execute("SELECT * FROM memberships WHERE user_id = ?", (user_id,))]

    def member_ids(self, club_id):
        return [r["user_id"] for r in self.conn.execute(
            "SELECT user_id FROM memberships WHERE club_id = ? ORDER BY user_id", (club_id,))]

    # ---- events ----
    def add_event(self, event: Event) -> Event:
        event.event_id = self.conn.execute(
            "INSERT INTO events (club_id, event_name, description, event_date, start_time, "
            "end_time, location, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (event.club_id, event.event_name, event.description, event.event_date,
             event.start_time, event.end_time, event.location, event.status.value)).lastrowid
        return event

    def get_event(self, event_id):
        row = self.conn.execute(_EVENT_SELECT + " WHERE e.event_id = ?", (event_id,)).fetchone()
        return Event.from_row(row) if row else None

    def update_event(self, event: Event):
        self.conn.execute(
            "UPDATE events SET event_name = ?, description = ?, event_date = ?, start_time = ?, "
            "end_time = ?, location = ?, status = ? WHERE event_id = ?",
            (event.event_name, event.description, event.event_date, event.start_time,
             event.end_time, event.location, event.status.value, event.event_id))

    def set_event_status(self, event_id, status):
        self.conn.execute("UPDATE events SET status = ? WHERE event_id = ?",
                          (EventStatus(status).value, event_id))

    def find_events(self, event_date, statuses):
        marks = ",".join("?" * len(statuses))
        rows = self.conn.execute(
            f"{_EVENT_SELECT} WHERE e.event_date = ? AND e.status IN ({marks}) ORDER BY e.start_time",
            (event_date, *[EventStatus(s).value for s in statuses]))
        return [Event.from_row(r) for r in rows]

    def events_for_club(self, club_id, statuses=None):
        sql, params = _EVENT_SELECT + " WHERE e.club_id = ?", [club_id]
        if statuses:
            sql += f" AND e.status IN ({','.join('?' * len(statuses))})"
            params += [EventStatus(s).value for s in statuses]
        return [Event.from_row(r) for r in
                self.conn.execute(sql + " ORDER BY e.event_date, e.start_time", params)]

    def find_duplicate(self, event: Event, exclude_event_id=None):
        row = self.conn.execute(
            _EVENT_SELECT + " WHERE e.club_id = ? AND e.event_name = ? AND e.event_date = ? "
            "AND e.start_time = ? AND e.end_time = ? AND e.status != 'cancelled' AND e.event_id IS NOT ?",
            (event.club_id, event.event_name, event.event_date, event.start_time,
             event.end_time, exclude_event_id)).fetchone()
        return Event.from_row(row) if row else None

    def search_events(self, *, keyword=None, club_id=None, event_date=None, location=None,
                      manage_club_ids=()):
        """Role-filtered read. Everyone sees confirmed events; officers also see the
        tentative events of the clubs they are officers of. Cancelled events are hidden."""
        manage = sorted(manage_club_ids)
        if manage:
            where = [f"(e.status = 'confirmed' OR (e.status = 'tentative' AND e.club_id IN ({','.join('?' * len(manage))})))"]
            params = list(manage)
        else:
            where, params = ["e.status = 'confirmed'"], []
        if keyword:
            where.append("(e.event_name LIKE ? ESCAPE '\\' OR e.description LIKE ? ESCAPE '\\' "
                         "OR e.location LIKE ? ESCAPE '\\' OR c.club_name LIKE ? ESCAPE '\\')")
            params += [_like(keyword)] * 4
        if club_id:
            where.append("e.club_id = ?")
            params.append(club_id)
        if event_date:
            where.append("e.event_date = ?")
            params.append(event_date)
        if location:
            where.append("e.location LIKE ? ESCAPE '\\'")
            params.append(_like(location))
        rows = self.conn.execute(
            f"{_EVENT_SELECT} WHERE {' AND '.join(where)} ORDER BY e.event_date, e.start_time, e.event_id",
            params)
        return [Event.from_row(r) for r in rows]

    # ---- notifications ----
    def add_notification(self, n: Notification) -> Notification:
        n.notification_id = self.conn.execute(
            "INSERT INTO notifications (user_id, event_id, message, read_status) VALUES (?, ?, ?, 0)",
            (n.user_id, n.event_id, n.message)).lastrowid
        return n

    def get_notifications(self, user_id, limit=50):
        return [Notification.from_row(r) for r in self.conn.execute(
            "SELECT * FROM notifications WHERE user_id = ? ORDER BY notification_id DESC LIMIT ?",
            (user_id, limit))]

    def count_unread(self, user_id) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM notifications WHERE user_id = ? AND read_status = 0",
                                 (user_id,)).fetchone()[0]

    def mark_notification_read(self, notification_id, user_id) -> bool:
        return self.conn.execute(
            "UPDATE notifications SET read_status = 1 WHERE notification_id = ? AND user_id = ?",
            (notification_id, user_id)).rowcount > 0
