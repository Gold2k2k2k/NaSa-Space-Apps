"""A bounded, thread-safe LRU of immutable analysis snapshots."""
from __future__ import annotations

import copy
import json
from collections import OrderedDict
from threading import RLock

from app.canonical import sha256_of


class SnapshotLimit(ValueError):
    pass


class SnapshotConflict(ValueError):
    pass


class RunStore:
    def __init__(self, *, max_entries=16, max_bytes=64 * 1024 * 1024):
        if max_entries < 1 or max_bytes < 1:
            raise ValueError("Run-store limits must be positive")
        self.max_entries, self.max_bytes = max_entries, max_bytes
        self._values = OrderedDict()
        self._bytes_used = 0
        self._lock = RLock()

    @property
    def bytes_used(self):
        with self._lock:
            return self._bytes_used

    def __len__(self):
        with self._lock:
            return len(self._values)

    def put(self, data):
        snapshot = copy.deepcopy(data)
        size = len(json.dumps(snapshot, ensure_ascii=False, allow_nan=False,
                              separators=(",", ":")).encode("utf-8"))
        if size > self.max_bytes:
            raise SnapshotLimit("Analysis exceeds the in-memory snapshot limit; use a smaller archive or AOI")
        identity, digest = snapshot["run_id"], sha256_of(snapshot)
        with self._lock:
            existing = self._values.get(identity)
            if existing is not None:
                if existing[2] != digest:
                    raise SnapshotConflict("An immutable run ID cannot contain different content")
                self._values.move_to_end(identity)
                return
            while self._values and (len(self._values) >= self.max_entries or self._bytes_used + size > self.max_bytes):
                _, (_, removed_size, _) = self._values.popitem(last=False)
                self._bytes_used -= removed_size
            self._values[identity] = (snapshot, size, digest)
            self._bytes_used += size

    def get(self, identity):
        with self._lock:
            found = self._values.get(identity)
            if found is None:
                return None
            self._values.move_to_end(identity)
            return copy.deepcopy(found[0])
