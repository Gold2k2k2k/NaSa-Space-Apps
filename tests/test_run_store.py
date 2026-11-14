"""Concurrency and snapshot isolation for the bounded run store."""
import unittest
from concurrent.futures import ThreadPoolExecutor


class TestRunStore(unittest.TestCase):
    def test_snapshots_are_copied_on_both_sides_and_ids_are_immutable(self):
        from app.run_store import RunStore
        store = RunStore(max_entries=3, max_bytes=10000)
        data = {"run_id": "one", "value": {"nested": 1}}
        store.put(data)
        data["value"]["nested"] = 2
        received = store.get("one")
        self.assertEqual(received["value"]["nested"], 1)
        received["value"]["nested"] = 3
        self.assertEqual(store.get("one")["value"]["nested"], 1)
        with self.assertRaises(ValueError):
            store.put({"run_id": "one", "value": "different content"})

    def test_recent_access_and_byte_limits_control_eviction(self):
        from app.run_store import RunStore
        store = RunStore(max_entries=2, max_bytes=1000)
        store.put({"run_id": "a"})
        store.put({"run_id": "b"})
        store.get("a")
        store.put({"run_id": "c"})
        self.assertIsNone(store.get("b"))
        self.assertIsNotNone(store.get("a"))
        with self.assertRaises(ValueError):
            store.put({"run_id": "huge", "value": "x" * 1001})
        self.assertLessEqual(store.bytes_used, 1000)

    def test_concurrent_reads_and_writes_return_whole_snapshots(self):
        from app.run_store import RunStore
        store = RunStore(max_entries=8, max_bytes=10000)
        def work(number):
            key = str(number)
            store.put({"run_id": key, "values": [number] * 20})
            result = store.get(key)
            if result is not None:
                self.assertEqual(result["values"], [number] * 20)
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(work, range(100)))
        self.assertLessEqual(len(store), 8)
        self.assertLessEqual(store.bytes_used, 10000)
