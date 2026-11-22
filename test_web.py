from app import app
from tests.test_app import Base, data
from seed import PASSWORD


class TestWeb(Base):
    def setUp(self):
        super().setUp()
        self.old_database = app.config["DATABASE"]
        app.config["DATABASE"] = self.db_path
        self.addCleanup(app.config.update, DATABASE=self.old_database)
        self.officer_web = app.test_client()
        self.member_web = app.test_client()
        for client, email in ((self.officer_web, "officer@vortex.edu"),
                              (self.member_web, "member@vortex.edu")):
            self.assertEqual(client.get("/login").status_code, 200)
            response = self.submit(client, "/login", email=email, password=PASSWORD)
            self.assertIn("Club calendar", response.text)

    def submit(self, client, url, **fields):
        with client.session_transaction() as session:
            fields["token"] = session["token"]
        return client.post(url, data=fields, follow_redirects=True)

    def test_calendar_workflow(self):
        officer, member = self.officer_web, self.member_web
        values = data(club_id=self.robotics, event_type="Workshop")
        self.assertIn("required", self.submit(officer, "/events/new", **dict(values, location="")).text)
        self.assertIn("Event saved as tentative", self.submit(officer, "/events/new", **values).text)
        self.assertIn("That event already exists", self.submit(officer, "/events/new", **values).text)
        self.assertIn("overlaps another event", self.submit(officer, "/events/new", **dict(values,event_name="Other")).text)
        self.assertNotIn("Robot Demo", member.get("/calendar").text)
        event_id = self.s.calendar.view(self.officer).events[0].event_id
        url = f"/events/{event_id}"
        self.assertEqual(self.submit(member, "/events/new", **values).status_code, 403)
        self.assertEqual(self.submit(member, url + "/edit", **values).status_code, 403)
        self.assertEqual(self.submit(member, url + "/cancel").status_code, 403)
        self.assertIn("Only officers", self.submit(member, url + "/confirm").text)
        self.assertIn("Event confirmed.", self.submit(officer, url + "/confirm").text)
        for params in [{"event_type":"workshop"}, {"keyword":"robot"}, {"club_id":self.robotics},
                       {"date":"2026-12-01"}, {"location":"ENG"}, {"view":"month","month":"2026-12"}]:
            self.assertIn("Robot Demo", member.get("/calendar", query_string=params).text)
        self.assertNotIn("Robot Demo", member.get("/calendar?event_type=Match").text)
        self.assertIn("ENG 202", self.submit(officer, url+"/edit", **dict(values, location="ENG 202")).text)
        self.assertIn("Cancel event?", officer.get(url+"/cancel").text)
        self.assertIn("Event cancelled", self.submit(officer, url+"/cancel").text)
        self.assertNotIn("Robot Demo", member.get("/calendar").text)
        inbox = member.get("/notifications").text
        for action in ["confirmed","updated","cancelled"]:
            self.assertIn("was "+action, inbox)
        item = self.s.notifications.list_for(self.member.user_id)[0]
        self.assertIn(">Read<", self.submit(member, f"/notifications/{item.notification_id}/read").text)

    def test_session_and_invalid_login(self):
        client = self.member_web
        self.assertEqual(client.post("/logout").status_code, 400)
        self.assertIn("Sign in", self.submit(client, "/logout").text)
        self.assertEqual(client.get("/calendar").status_code, 302)
        self.assertIn("Invalid email or password", self.submit(client, "/login",
                      email="member@vortex.edu", password="incorrect").text)

    def test_calendar_pages_keep_filters_and_month_shows_all(self):
        for i in range(26):
            self.make(event_name=f"Talk {i:02d}")
        client = self.officer_web
        first = client.get("/calendar?keyword=Talk")
        self.assertIn("Page 1 of 2", first.text)
        self.assertIn("keyword=Talk&amp;page=2", first.text)
        self.assertNotIn("Talk 25", first.text)
        last = client.get("/calendar?keyword=Talk&page=2")
        self.assertIn("Talk 25", last.text)
        self.assertNotIn("Talk 00", last.text)
        self.assertIn("Talk 25", client.get("/calendar?view=month&month=2026-12").text)
        self.assertNotIn("Talk 25", self.member_web.get("/calendar?page=2").text)

    def test_inbox_filter_and_bulk_read(self):
        from models import Notification
        with self.storage.transaction():
            for i in range(52):
                self.storage.add_notification(Notification(self.member.user_id, f"Reminder {i}"))
            self.storage.add_notification(Notification(self.officer.user_id, "Officer reminder"))
        item = self.s.notifications.list_for(self.member.user_id)[0]
        inbox = self.submit(self.member_web, f"/notifications/{item.notification_id}/read?filter=unread")
        self.assertIn("51 unread", inbox.text)
        self.assertNotIn("Reminder 51", inbox.text)
        for _ in range(2):
            inbox = self.submit(self.member_web, "/notifications/read-all?filter=unread")
            self.assertIn("No unread notifications.", inbox.text)
        self.assertEqual(self.s.notifications.unread_count(self.officer.user_id), 1)

    def test_legacy_urls_use_current_event_workflow(self):
        client = self.officer_web
        self.assertIn("Club calendar", client.get("/officer-calendar").text)
        self.assertIn("Create event", client.get("/create-event").text)
        self.assertIn("Event saved as tentative", self.submit(client, "/create-event", **data(club_id=self.robotics)).text)
        event_id = self.s.calendar.view(self.officer).events[0].event_id
        self.assertIn("Edit event", client.get(f"/edit-event/{event_id}").text)
        self.assertIn("ENG 202", self.submit(client, f"/edit-event/{event_id}", **data(location="ENG 202")).text)
        self.assertIn("Event confirmed", self.submit(client, f"/confirm-event/{event_id}").text)
        self.assertIn("Event cancelled", self.submit(client, f"/cancel-event/{event_id}").text)
