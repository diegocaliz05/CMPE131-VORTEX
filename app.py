"""Vortex local web application."""
from calendar import Calendar
from datetime import date, timedelta
import os
import secrets
from pathlib import Path

from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for

from database import init_db
from seed import seed_demo_data
from services import DataStorage, Services

app = Flask(__name__)
app.config.update(SECRET_KEY=os.environ.get("VORTEX_SECRET_KEY") or secrets.token_hex(32),
                  DATABASE=os.environ.get("VORTEX_DB") or str(Path(__file__).with_name("vortex.db")),
                  SESSION_COOKIE_SAMESITE="Lax")


@app.before_request
def open_request():
    if request.endpoint in (None, "static"):
        return
    g.storage = DataStorage(db_path=app.config["DATABASE"])
    g.services = Services(g.storage)
    g.access = g.services.authentication.load_access(session.get("user_id"))
    if not g.access and request.endpoint not in ("login", "register"):
        return redirect(url_for("login"))
    if request.method == "POST":
        token = request.form.get("token", "")
        if not token or not secrets.compare_digest(session.get("token", ""), token):
            abort(400)
    if "token" not in session:
        session["token"] = secrets.token_hex(24)


@app.teardown_request
def close_request(error):
    if "storage" in g:
        g.storage.close()


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        result = g.services.authentication.login(request.form.get("email"), request.form.get("password"))
        if result.ok:
            session.clear()
            session.update(result.session)
            return redirect(url_for("calendar"))
        flash(result.error)
    return render_template("login.html", register=False)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        result = g.services.authentication.register(request.form.get("name"), request.form.get("email"),
                                                    request.form.get("password"))
        if result.ok:
            flash("Account created. Sign in to view the calendar.")
            return redirect(url_for("login"))
        flash(" ".join(f"{field}: {error}" for field, error in result.errors.items()) or result.message)
    return render_template("login.html", register=True)


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.get("/officer-calendar")
@app.get("/")
@app.get("/events")
@app.get("/calendar")
def calendar():
    filters = {key: request.args.get(key) for key in ("keyword", "club_id", "date", "location", "event_type")}
    result = g.services.search.search(g.access, **filters)
    if not result.ok:
        flash(result.message)
    weeks = []
    month = previous = following = None
    if request.args.get("view") == "month":
        try:
            month = date.fromisoformat(request.args.get("month", "") + "-01")
        except ValueError:
            month = date.today().replace(day=1)
        if month.year < 2 or month.year > 9998:
            abort(400)
        weeks = Calendar().monthdayscalendar(month.year, month.month)
        previous = (month - timedelta(days=1)).strftime("%Y-%m")
        following = (month + timedelta(days=32)).strftime("%Y-%m")
    def view_url(view, month_value=None):
        args = request.args.to_dict()
        args.pop("page", None)
        args.update(view=view)
        if month_value:
            args["month"] = month_value
        return url_for("calendar", **args)
    events = result.events
    page_size = 25
    pages = max(1, (len(events) + page_size - 1) // page_size)
    page = min(pages, max(1, request.args.get("page", default=1, type=int)))
    if month is None:
        events = events[(page - 1) * page_size:page * page_size]

    def page_url(number):
        return url_for("calendar", **dict(request.args.to_dict(), page=number))

    return render_template("calendar.html", events=events, page=page, pages=pages, page_url=page_url, clubs=g.storage.list_clubs(),
                           month=month, weeks=weeks, previous=previous, following=following,
                           view_url=view_url)


@app.route("/create-event", methods=["GET", "POST"])
@app.route("/edit-event/<int:event_id>", methods=["GET", "POST"])
@app.route("/events/new", methods=["GET", "POST"])
@app.route("/events/<int:event_id>/edit", methods=["GET", "POST"])
def event_form(event_id=None):
    clubs = [c for c in g.storage.list_clubs() if g.access.is_officer_of(c.club_id)]
    if not clubs:
        abort(403)
    values = {}
    if event_id is not None:
        event = g.storage.get_event(event_id)
        if event is None:
            abort(404)
        if not g.access.is_officer_of(event.club_id):
            abort(403)
        values = event.to_dict()
    result = None
    if request.method == "POST":
        values.update(request.form.to_dict())
        acknowledged = request.form.get("ack") == "yes"
        if event_id is None:
            result = g.services.events.create_event(g.access, request.form.get("club_id", type=int),
                                                    values, acknowledged)
        else:
            result = g.services.events.edit_event(g.access, event_id, values, acknowledged)
        flash(result.message)
        if result.ok:
            return redirect(url_for("calendar"))
    return render_template("create_event.html", values=values, clubs=clubs, result=result, editing=event_id is not None)


@app.post("/confirm-event/<int:event_id>")
@app.post("/events/<int:event_id>/confirm")
def confirm(event_id):
    flash(g.services.events.confirm_event(g.access, event_id).message)
    return redirect(url_for("calendar"))


@app.post("/cancel-event/<int:event_id>")
@app.route("/events/<int:event_id>/cancel", methods=["GET", "POST"])
def cancel(event_id):
    event = g.storage.get_event(event_id)
    if not event:
        abort(404)
    if not g.access.is_officer_of(event.club_id):
        abort(403)
    if request.method == "POST":
        flash(g.services.events.cancel_event(g.access, event_id, confirmed=True).message)
        return redirect(url_for("calendar"))
    return render_template("cancel.html", event=event)


@app.get("/notifications")
def notifications():
    unread_only = request.args.get("filter") == "unread"
    inbox = g.services.notifications
    return render_template("notifications.html", items=inbox.list_for(g.access.user_id, unread_only),
                           unread=inbox.unread_count(g.access.user_id), unread_only=unread_only)


@app.post("/notifications/read-all")
def read_all_notifications():
    g.services.notifications.mark_all_read(g.access.user_id)
    return redirect(url_for("notifications", filter=request.args.get("filter")))


@app.post("/notifications/<int:item_id>/read")
def read_notification(item_id):
    g.services.notifications.mark_read(item_id, g.access.user_id)
    return redirect(url_for("notifications", filter=request.args.get("filter")))


def prepare_database():
    init_db(app.config["DATABASE"])
    storage = DataStorage(db_path=app.config["DATABASE"])
    try:
        if not storage.list_clubs():
            seed_demo_data(storage)
    finally:
        storage.close()



if __name__ == "__main__":
    prepare_database()
    app.run()
