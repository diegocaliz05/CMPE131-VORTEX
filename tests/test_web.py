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
