"""Vortex tests, one class per component, driven through the service classes (no HTML needed).
Run everything:   py -m unittest discover -s tests -t . -v
Run one component: py -m unittest tests.test_app.TestAuthentication -v
T-xx ids are the SAD section 8 validation tests."""
import logging
import os
import sqlite3
import tempfile
import time
import unittest

from database import init_db
from models import Club, Event, EventStatus, Role
from seed import PASSWORD, seed_demo_data
from services import DataStorage, Services
from services import results as R

logging.disable(logging.CRITICAL)


def data(**kw):
    base = {"event_name": "Robot Demo", "description": "Show and tell", "event_date": "2026-12-01",
            "start_time": "10:00", "end_time": "11:00", "location": "ENG 101"}
    base.update(kw)
    return base


class Base(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self._dir.name, "test.db")
        init_db(self.db_path)
        self.storage = DataStorage(db_path=self.db_path)
        self.ids = seed_demo_data(self.storage)
        self.s = Services(self.storage)
        load = self.s.authentication.load_access
        self.officer = load(self.ids["officer"])     # officer: Robotics, member: Chess
        self.officer2 = load(self.ids["officer2"])   # officer: Chess
        self.member = load(self.ids["member"])       # member: Robotics
        self.robotics, self.chess = self.ids["robotics"], self.ids["chess"]

    def tearDown(self):
        self.storage.close()
        self._dir.cleanup()

    def make(self, access=None, club=None, confirm=False, **kw):
        r = self.s.events.create_event(access or self.officer, club or self.robotics, data(**kw), True)
        self.assertTrue(r.ok, r.message)
        if confirm:
            self.assertTrue(self.s.events.confirm_event(access or self.officer, r.event.event_id).ok)
        return r.event

    def count(self, table):
        return self.storage.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


class TestModels(unittest.TestCase):
    def ev(self, **kw):
        base = dict(club_id=1, event_name="E", event_date="2026-12-01", start_time="10:00",
                    end_time="11:00", location="A")
        base.update(kw)
        return Event(**base)

    def test_overlap_rules(self):
        e = self.ev()
        self.assertTrue(e.overlaps("2026-12-01", "10:30", "11:30"))
        self.assertFalse(e.overlaps("2026-12-01", "11:00", "12:00"))   # back to back
        self.assertFalse(e.overlaps("2026-12-02", "10:00", "11:00"))   # other day

    def test_status_transitions(self):
        e = self.ev()
        self.assertTrue(e.can_transition_to(EventStatus.CONFIRMED))
        e.status = EventStatus.CANCELLED
        self.assertFalse(e.can_transition_to(EventStatus.CONFIRMED))

    def test_user_record_has_no_role_or_club(self):
        from models import User
        self.assertEqual({"name", "email", "password_hash", "user_id"}, set(User.__dataclass_fields__))


class TestDataStorage(Base):
    def test_records_round_trip_and_match_schema(self):
        club = self.storage.get_club(self.robotics)
        self.assertEqual((club.club_name, type(club).__name__), ("Robotics Club", "Club"))
        user = self.storage.get_user_by_email("OFFICER@vortex.edu")
        self.assertEqual(user.user_id, self.ids["officer"])
        self.assertTrue(all(m.role in Role for m in self.storage.get_memberships(user.user_id)))

    def test_club_methods(self):
        club = self.storage.get_club(self.chess)
        with self.storage.transaction():
            club.add_member(self.storage, self.ids["member"], Role.MEMBER)
        self.assertIn(self.ids["member"], self.storage.member_ids(self.chess))
        with self.storage.transaction():
            club.remove_member(self.storage, self.ids["member"])
        self.assertNotIn(self.ids["member"], self.storage.member_ids(self.chess))
        self.make(self.officer2, self.chess, location="Library")
        self.assertEqual(len(club.get_events(self.storage)), 1)

    def test_transaction_rolls_back(self):
        with self.assertRaises(RuntimeError):
            with self.storage.transaction():
                self.storage.add_club(Club("Temp"))
                raise RuntimeError
        self.assertEqual(self.count("clubs"), 2)

    def test_unique_index_backstop(self):
        self.make()
        with self.assertRaises(sqlite3.IntegrityError):
            self.storage.conn.execute("INSERT INTO events (club_id,event_name,event_date,start_time,end_time,status)"
                                      " VALUES (1,'Robot Demo','2026-12-01','10:00','11:00','tentative')")

    def test_foreign_keys_enforced(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.storage.conn.execute("INSERT INTO memberships (user_id, club_id, role) VALUES (999, 1, 'member')")


class TestAuthentication(Base):
    def test_T01_valid_login(self):
        r = self.s.authentication.login("officer@vortex.edu", PASSWORD)
        self.assertTrue(r.ok)
        self.assertEqual(r.session, {"user_id": self.ids["officer"]})
        self.assertEqual({m.club_id: m.role for m in r.memberships},
                         {self.robotics: Role.OFFICER, self.chess: Role.MEMBER})

    def test_T02_bad_credentials(self):
        for email, pw in [("officer@vortex.edu", "wrong"), ("nobody@x.edu", PASSWORD), ("", "")]:
            r = self.s.authentication.login(email, pw)
            self.assertFalse(r.ok)
            self.assertEqual(r.error, "Invalid email or password.")
            self.assertEqual(r.session, {})

    def test_officer_is_user_plus_filtered_memberships(self):
        self.assertTrue(self.officer.is_officer)
        self.assertEqual([m.club_id for m in self.officer.authorized_clubs], [self.robotics])
        self.assertFalse(self.officer.is_officer_of(self.chess))
        self.assertFalse(self.member.is_officer)

    def test_password_stored_hashed_and_not_logged(self):
        row = self.storage.conn.execute("SELECT password_hash FROM users WHERE user_id=1").fetchone()
        self.assertNotIn(PASSWORD, row["password_hash"])
        self.assertNotIn("password_hash", repr(self.officer.user))

    def test_logout_returns_empty_session(self):
        self.assertEqual(self.s.authentication.logout(), {})

    def test_register_validation_and_duplicates(self):
        r = self.s.authentication.register("", "bad", "short")
        self.assertEqual((r.code, set(r.errors)), (R.INVALID, {"name", "email", "password"}))
        self.assertEqual(self.s.authentication.register("X", "officer@vortex.edu", "longenough1").code, R.DUPLICATE)


class TestEventManagement(Base):
    def test_T03_create_saves_tentative(self):
        r = self.s.events.create_event(self.officer, self.robotics, data())
        self.assertTrue(r.ok)
        self.assertEqual(self.storage.get_event(r.event.event_id).status, EventStatus.TENTATIVE)

    def test_T04_missing_and_invalid_fields(self):
        for field in ("event_name", "event_date", "start_time", "end_time", "location"):
            r = self.s.events.create_event(self.officer, self.robotics, data(**{field: ""}))
            self.assertEqual((r.code, field in r.errors), (R.INVALID, True), field)
        for bad in [dict(event_date="12/01/2026"), dict(start_time="25:00"), dict(start_time="12:00", end_time="11:00")]:
            self.assertEqual(self.s.events.create_event(self.officer, self.robotics, data(**bad)).code, R.INVALID)
        self.assertEqual(self.count("events"), 0)

    def test_T08_members_and_other_club_officers_denied(self):
        ev = self.make()
        e = self.s.events
        for denied in (e.create_event(self.member, self.robotics, data(event_name="X")),
                       e.create_event(self.officer, self.chess, data(event_name="Y")),   # only a Chess member
                       e.edit_event(self.member, ev.event_id, data()),
                       e.confirm_event(self.officer2, ev.event_id),
                       e.cancel_event(self.member, ev.event_id, True)):
            self.assertEqual(denied.code, R.DENIED)
        self.assertEqual(self.storage.get_event(ev.event_id).status, EventStatus.TENTATIVE)

    def test_T05_create_conflict_warning_then_acknowledge(self):
        self.make()
        r = self.s.events.create_event(self.officer, self.robotics, data(event_name="B", start_time="10:30"))
        self.assertEqual((r.code, len(r.conflicts)), (R.CONFLICT, 1))
        self.assertEqual(self.count("events"), 1)
        self.assertTrue(self.s.events.create_event(self.officer, self.robotics,
                        data(event_name="B", start_time="10:30"), acknowledge_conflicts=True).ok)

    def test_T06_confirm(self):
        ev = self.make()
        r = self.s.events.confirm_event(self.officer, ev.event_id)
        self.assertEqual(r.event.status, EventStatus.CONFIRMED)
        self.assertEqual(self.s.events.confirm_event(self.officer, ev.event_id).code, R.BAD_STATE)

    def test_confirm_conflict_returns_warning_and_leaves_status(self):
        self.make(confirm=True)
        clash = self.make(event_name="Clash", start_time="10:15", end_time="10:45")
        r = self.s.events.confirm_event(self.officer, clash.event_id)
        self.assertEqual(r.code, R.CONFLICT)
        self.assertEqual(self.storage.get_event(clash.event_id).status, EventStatus.TENTATIVE)
        self.assertEqual(self.count("notifications"), 2)  # only the first confirmation notified (2 club members)

    def test_two_tentative_events_can_still_be_confirmed_one_at_a_time(self):
        a = self.make()
        b = self.make(event_name="B")
        self.assertTrue(self.s.events.confirm_event(self.officer, a.event_id).ok)
        self.assertEqual(self.s.events.confirm_event(self.officer, b.event_id).code, R.CONFLICT)

    def test_T09_cancel_needs_confirmation_flag(self):
        ev = self.make(confirm=True)
        self.assertEqual(self.s.events.cancel_event(self.officer, ev.event_id).code, R.CONFIRM_REQUIRED)
        self.assertEqual(self.storage.get_event(ev.event_id).status, EventStatus.CONFIRMED)
        r = self.s.events.cancel_event(self.officer, ev.event_id, confirmed=True)
        self.assertEqual(r.event.status, EventStatus.CANCELLED)
        self.assertEqual(self.s.events.cancel_event(self.officer, ev.event_id, True).code, R.BAD_STATE)
        self.assertEqual(self.s.events.confirm_event(self.officer, ev.event_id).code, R.BAD_STATE)

    def test_cancelled_event_frees_slot(self):
        ev = self.make(confirm=True)
        self.s.events.cancel_event(self.officer, ev.event_id, True)
        self.assertTrue(self.s.events.create_event(self.officer, self.robotics, data()).ok)

    def test_T12_duplicate_prevention(self):
        self.make()
        self.assertEqual(self.s.events.create_event(self.officer, self.robotics, data(), True).code, R.DUPLICATE)
        self.assertEqual(self.count("events"), 1)

    def test_edit_confirmed_notifies_and_blocks_on_confirmed_conflict(self):
        ev = self.make(confirm=True)
        other = self.make(event_name="Other", event_date="2026-12-02", location="ENG 202", confirm=True)
        self.assertTrue(self.s.events.edit_event(self.officer, ev.event_id, data(location="ENG 303")).ok)
        self.assertEqual(self.s.events.edit_event(self.officer, other.event_id,
                         data(event_name="Other", event_date="2026-12-01", location="ENG 303")).code, R.CONFLICT)
        self.assertEqual(self.count("notifications"), 6)  # 2 members x (confirm, confirm, one successful edit)

    def test_storage_failure_rolls_back_and_returns_error(self):
        ev = self.make()
        from exceptions import StorageError
        def boom(*a, **k): raise StorageError("disk")
        self.storage.set_event_status = boom
        r = self.s.events.confirm_event(self.officer, ev.event_id)
        self.assertEqual(r.code, R.STORAGE_ERROR)
        self.assertEqual(self.storage.get_event(ev.event_id).status, EventStatus.TENTATIVE)


class TestConflictDetection(Base):
    def test_check_is_read_only_and_matches_location_and_time(self):
        self.make()
        c = self.s.conflicts.check
        self.assertTrue(c("2026-12-01", "10:30", "11:30", "eng 101").has_conflict)   # case-insensitive
        self.assertFalse(c("2026-12-01", "11:00", "12:00", "ENG 101").has_conflict)  # back to back
        self.assertFalse(c("2026-12-01", "10:30", "11:30", "Library").has_conflict)  # other room
        self.assertFalse(c("2026-12-02", "10:30", "11:30", "ENG 101").has_conflict)  # other day
        self.assertEqual(self.count("events"), 1)

    def test_other_clubs_in_same_room_conflict(self):
        self.make()
        r = self.s.events.create_event(self.officer2, self.chess, data(event_name="Chess"))
        self.assertEqual(r.code, R.CONFLICT)

    def test_cancelled_events_ignored_and_exclude_self(self):
        ev = self.make()
        self.assertFalse(self.s.conflicts.check("2026-12-01", "10:00", "11:00", "ENG 101",
                                                exclude_event_id=ev.event_id).has_conflict)
        self.s.events.cancel_event(self.officer, ev.event_id, True)
        self.assertFalse(self.s.conflicts.check("2026-12-01", "10:00", "11:00", "ENG 101").has_conflict)


class TestNotifications(Base):
    def inbox(self, access):
        return [n.message for n in self.s.notifications.list_for(access.user_id)]

    def test_T11_confirm_update_cancel_notify_club_members(self):
        ev = self.make()
        self.assertEqual(self.inbox(self.member), [])   # tentative creation never notifies
        self.s.events.confirm_event(self.officer, ev.event_id)
        self.s.events.edit_event(self.officer, ev.event_id, data(location="ENG 202"))
        self.s.events.cancel_event(self.officer, ev.event_id, True)
        msgs = self.inbox(self.member)
        self.assertEqual(len(msgs), 3)
        self.assertTrue("cancelled" in msgs[0] and "updated" in msgs[1] and "confirmed" in msgs[2])
        self.assertEqual(self.inbox(self.officer2), [])  # other club untouched

    def test_one_row_per_member(self):
        self.make(confirm=True)
        self.assertEqual(self.count("notifications"), 2)  # officer + member of Robotics

    def test_cancelling_tentative_does_not_notify(self):
        ev = self.make()
        self.s.events.cancel_event(self.officer, ev.event_id, True)
        self.assertEqual(self.count("notifications"), 0)

    def test_failure_is_swallowed_and_event_still_saved(self):
        ev = self.make()
        self.storage.add_notification = lambda n: (_ for _ in ()).throw(sqlite3.OperationalError("x"))
        self.assertTrue(self.s.events.confirm_event(self.officer, ev.event_id).ok)
        self.assertEqual(self.storage.get_event(ev.event_id).status, EventStatus.CONFIRMED)

    def test_mark_read_scoped_to_owner(self):
        self.make(confirm=True)
        n = self.s.notifications.list_for(self.member.user_id)[0]
        self.assertFalse(self.s.notifications.mark_read(n.notification_id, self.officer2.user_id))
        self.assertTrue(self.s.notifications.mark_read(n.notification_id, self.member.user_id))
        self.assertEqual(self.s.notifications.unread_count(self.member.user_id), 0)


class TestCalendarAndSearch(Base):
    def setUp(self):
        super().setUp()
        self.make(event_name="Hack Night", description="Soldering workshop", confirm=True)
        self.make(event_name="Secret Plan", event_date="2026-12-02")
        self.make(self.officer2, self.chess, event_name="Blitz Chess", event_date="2026-12-03",
                  location="Library", confirm=True)
        self.make(self.officer2, self.chess, event_name="Chess Surprise", event_date="2026-12-04", location="Library")
        gone = self.make(event_name="Old", event_date="2026-12-05")
        self.s.events.cancel_event(self.officer, gone.event_id, True)

    def names(self, access, **f):
        return {e.event_name for e in self.s.search.search(access, **f).events}

    def test_T07_member_sees_only_confirmed(self):
        view = self.s.calendar.view(self.member)
        self.assertEqual(view.view, "member")
        self.assertEqual({e.event_name for e in view.events}, {"Hack Night", "Blitz Chess"})

    def test_officer_sees_own_tentative_only(self):
        self.assertEqual({e.event_name for e in self.s.calendar.view(self.officer).events},
                         {"Hack Night", "Secret Plan", "Blitz Chess"})
        self.assertEqual({e.event_name for e in self.s.calendar.view(self.officer2).events},
                         {"Hack Night", "Blitz Chess", "Chess Surprise"})

    def test_calendar_groups_by_date(self):
        self.assertEqual(list(self.s.calendar.view(self.officer).by_date), ["2026-12-01", "2026-12-02", "2026-12-03"])

    def test_T10_filters(self):
        self.assertEqual(self.names(self.member, keyword="solder"), {"Hack Night"})
        self.assertEqual(self.names(self.member, keyword="robotics"), {"Hack Night"})
        self.assertEqual(self.names(self.member, club_id=self.chess), {"Blitz Chess"})
        self.assertEqual(self.names(self.member, date="2026-12-03"), {"Blitz Chess"})
        self.assertEqual(self.names(self.member, location="lib"), {"Blitz Chess"})
        self.assertEqual(self.names(self.officer, keyword="secret"), {"Secret Plan"})

    def test_no_match_message(self):
        r = self.s.search.search(self.member, keyword="zzz")
        self.assertEqual((r.ok, r.events, r.message), (True, [], "No events found"))

    def test_bad_date_and_injection_safe(self):
        self.assertEqual(self.s.search.search(self.member, date="tomorrow").code, R.INVALID)
        self.assertEqual(self.names(self.member, keyword="%"), set())
        self.assertEqual(self.names(self.member, keyword="'; DROP TABLE events;--"), set())
        self.assertEqual(self.count("events"), 5)

    def test_get_event_hides_tentative_from_others(self):
        tent = self.storage.search_events(keyword="Secret", manage_club_ids=[self.robotics])[0]
        self.assertEqual(self.s.events.get_event(self.member, tent.event_id).code, R.NOT_FOUND)
        self.assertTrue(self.s.events.get_event(self.officer, tent.event_id).ok)


class TestPerformance(Base):
    """SAD 6.2 / 7.1: calendar < 3 s, search < 2 s, login < 2 s."""
    def test_large_calendar_and_search(self):
        rows = [(self.robotics if i % 2 else self.chess, f"Event {i}", "d", f"2026-{1 + i % 12:02d}-{1 + i % 28:02d}",
                 "09:00", "10:00", f"Room {i % 50}", "confirmed") for i in range(3000)]
        self.storage.conn.executemany("INSERT INTO events (club_id,event_name,description,event_date,start_time,"
                                      "end_time,location,status) VALUES (?,?,?,?,?,?,?,?)", rows)
        self.storage.conn.commit()
        for label, limit, fn in [
            ("calendar", 3.0, lambda: self.s.calendar.view(self.officer)),
            ("search", 2.0, lambda: self.s.search.search(self.member, keyword="Event 12", location="Room 1")),
            ("conflict", 1.0, lambda: self.s.conflicts.check("2026-01-01", "09:00", "10:00", "Room 1"))]:
            t = time.perf_counter()
            fn()
            self.assertLess(time.perf_counter() - t, limit, label)

    def test_login_speed(self):
        t = time.perf_counter()
        self.assertTrue(self.s.authentication.login("officer@vortex.edu", PASSWORD).ok)
        self.assertLess(time.perf_counter() - t, 2.0)

    def test_second_connection_sees_committed_data(self):
        other = DataStorage(db_path=self.db_path)
        ev = self.make(confirm=True)
        self.assertEqual([e.event_id for e in other.search_events()], [ev.event_id])
        other.close()


if __name__ == "__main__":
    unittest.main()
