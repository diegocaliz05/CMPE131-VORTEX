# Vortex class structure

```
models/    user.py (User, Membership, Role, Access)  club.py  event.py  notification.py
services/  authentication  event_management  conflict_detection  calendar_display
           search  notifications  data_storage  results
```
- Records match schema.sql field for field. `User` has no role/club; `Membership` carries them.
- An officer is a `User` plus officer memberships (`Access.authorized_clubs` is a filtered view).
- `DataStorage` is the only class that runs SQL. Writes never commit; services own transactions.
- Components return `services.results.Result` for expected outcomes; only storage errors raise.
- `services.Services` wires the seven components around one `DataStorage`.
- Not covered yet: event type search (no `type` column in `events`).

Tests: `py -m unittest discover -s tests -t . -v` (one class: `-m unittest tests.test_app.TestAuthentication`).
Needs Flask installed (Authentication uses Werkzeug's password hashing).
