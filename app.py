from flask import Flask, render_template, request, redirect
from database import init_db
from services import DataStorage, Services


app = Flask(__name__)

# Make sure the database tables exist
init_db()

# Connect Vortex to the database and backend services
storage = DataStorage()
services = Services(storage)


@app.route("/")
def home():
    return "Vortex is running!"


@app.route("/create-event", methods=["GET", "POST"])
def create_event():

    # TEMPORARY:
    # Use the seeded officer account until login is connected to Flask
    user = storage.get_user_by_email("officer@vortex.edu")

    if user is None:
        return "Run py seed.py first."

    access = services.authentication.load_access(user.user_id)

    if not access.authorized_clubs:
        return "Demo officer does not manage a club."

    club_id = access.authorized_clubs[0].club_id

    message = ""

    if request.method == "POST":

        event_data = {
            "event_name": request.form.get("event_name"),
            "description": request.form.get("description"),
            "event_date": request.form.get("event_date"),
            "start_time": request.form.get("start_time"),
            "end_time": request.form.get("end_time"),
            "location": request.form.get("location")
        }

        acknowledge = "acknowledge_conflicts" in request.form

        result = services.events.create_event(
            access,
            club_id,
            event_data,
            acknowledge_conflicts=acknowledge
        )

        message = result.message

    return render_template(
        "create_event.html",
        message=message
    )

@app.route("/officer-calendar")
def officer_calendar():

    user = storage.get_user_by_email("officer@vortex.edu")

    if user is None:
        return "Run py seed.py first."

    access = services.authentication.load_access(user.user_id)

    calendar = services.calendar.view(access)

    return render_template(
        "officer_calendar.html",
        events=calendar.events
    )

@app.route("/confirm-event/<int:event_id>", methods=["POST"])
def confirm_event(event_id):
    user = storage.get_user_by_email("officer@vortex.edu")

    if user is None:
        return "Run py seed.py first."

    access = services.authentication.load_access(user.user_id)

    result = services.events.confirm_event(access, event_id)

    return redirect("/officer-calendar")

@app.route("/cancel-event/<int:event_id>", methods=["POST"])
def cancel_event(event_id):
    user = storage.get_user_by_email("officer@vortex.edu")

    if user is None:
        return "Run py seed.py first."

    access = services.authentication.load_access(user.user_id)

    result = services.events.cancel_event(
        access,
        event_id,
        confirmed=True
    )

    return redirect("/officer-calendar")

@app.route("/edit-event/<int:event_id>", methods=["GET", "POST"])
def edit_event(event_id):
    user = storage.get_user_by_email("officer@vortex.edu")

    if user is None:
        return "Run py seed.py first."

    access = services.authentication.load_access(user.user_id)

    event_result = services.events.get_event(access, event_id)

    if not event_result.ok:
        return event_result.message

    event = event_result.event

    if request.method == "POST":
        event_data = {
            "event_name": request.form.get("event_name"),
            "description": request.form.get("description"),
            "event_date": request.form.get("event_date"),
            "start_time": request.form.get("start_time"),
            "end_time": request.form.get("end_time"),
            "location": request.form.get("location")
        }

        acknowledge = "acknowledge_conflicts" in request.form

        result = services.events.edit_event(
            access,
            event_id,
            event_data,
            acknowledge_conflicts=acknowledge
        )

        if result.ok:
            return redirect("/officer-calendar")

        return render_template(
            "edit_event.html",
            event=event,
            message=result.message
        )

    return render_template(
        "edit_event.html",
        event=event
    )

if __name__ == "__main__":
    app.run(debug=True)