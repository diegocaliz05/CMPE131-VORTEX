"""Demo data. Run `py seed.py` to populate vortex.db (idempotent)."""
from database import init_db
from models import Club, Role
from services import DataStorage, Services

PASSWORD = "password123"


def seed_demo_data(storage):
    s = Services(storage)
    if storage.get_user_by_email("officer@vortex.edu"):
        return {}
    with storage.transaction():
        robotics = storage.add_club(Club("Robotics Club", "Builds robots")).club_id
        chess = storage.add_club(Club("Chess Club", "Weekly tournaments")).club_id
    officer = s.authentication.register("Olivia Officer", "officer@vortex.edu", PASSWORD).user
    officer2 = s.authentication.register("Chet Chess", "chess.officer@vortex.edu", PASSWORD).user
    member = s.authentication.register("Mia Member", "member@vortex.edu", PASSWORD).user
    with storage.transaction():
        storage.add_membership(officer.user_id, robotics, Role.OFFICER)
        storage.add_membership(officer.user_id, chess, Role.MEMBER)
        storage.add_membership(officer2.user_id, chess, Role.OFFICER)
        storage.add_membership(member.user_id, robotics, Role.MEMBER)
    return {"robotics": robotics, "chess": chess, "officer": officer.user_id,
            "officer2": officer2.user_id, "member": member.user_id}


if __name__ == "__main__":
    init_db()
    store = DataStorage()
    print("seeded" if seed_demo_data(store) else "already seeded")
