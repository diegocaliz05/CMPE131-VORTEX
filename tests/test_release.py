from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from services import DataStorage, Services
from tests.test_app import Base, data


class TestRelease(Base):
    def test_event_type_round_trip_and_filter(self):
        workshop = self.make(confirm=True, event_type="Workshop")
        self.make(confirm=True, event_name="Chess match", event_date="2026-12-02", event_type="Match")
        results = self.s.search.search(self.member, event_type="workshop")
        self.assertEqual([event.event_id for event in results.events], [workshop.event_id])
        self.assertTrue(self.s.events.edit_event(self.officer, workshop.event_id, data()).ok)
        self.assertEqual(self.storage.get_event(workshop.event_id).event_type, "Workshop")

    def test_simultaneous_confirmations_share_one_slot(self):
        ids = [self.make(event_name=name).event_id for name in ("Demo A", "Demo B")]
        start = Barrier(2)

        def confirm(event_id):
            storage = DataStorage(db_path=self.db_path)
            try:
                services = Services(storage)
                start.wait(timeout=5)
                return services.events.confirm_event(self.officer, event_id).code
            finally:
                storage.close()

        with ThreadPoolExecutor(2) as pool:
            self.assertCountEqual(pool.map(confirm, ids), ["ok", "conflict"])
        self.assertEqual(len(self.s.calendar.view(self.member).events), 1)
