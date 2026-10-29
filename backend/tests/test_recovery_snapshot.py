"""Offline snapshot tests with isolated temporary SQLite databases."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from recovery import RecoveryValidationError, create_snapshot, verify_snapshot


class OfflineRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source.sqlite3"
        self.snapshot = self.root / "snapshot.sqlite3"
        with sqlite3.connect(self.source) as db:
            db.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
            db.execute("INSERT INTO sessions VALUES (?, ?)",
                       ("session-a", json.dumps({"id": "session-a", "events": [],
                                                  "config": {"num_rounds": 1}})))

    def test_consistent_snapshot_and_offline_integrity(self):
        result = create_snapshot(str(self.source), str(self.snapshot))
        self.assertEqual(result["sessions_validated"], 1)
        self.assertEqual(len(result["sha256"]), 64)
        self.assertEqual(result, verify_snapshot(str(self.snapshot)))
        with sqlite3.connect(self.source) as db:
            db.execute("INSERT INTO sessions VALUES (?, ?)",
                       ("session-b", json.dumps({"id": "session-b", "events": [], "config": {}})))
        self.assertEqual(verify_snapshot(str(self.snapshot))["sessions_validated"], 1)

    def test_never_overwrite_existing_good_snapshot(self):
        create_snapshot(str(self.source), str(self.snapshot))
        with self.assertRaises(RecoveryValidationError):
            create_snapshot(str(self.source), str(self.snapshot))
        with self.assertRaises(RecoveryValidationError):
            create_snapshot(str(self.source), str(self.source))

    def test_bad_json_and_mismatched_identity_are_rejected(self):
        with sqlite3.connect(self.source) as db:
            db.execute("UPDATE sessions SET payload = ?", ('not JSON',))
        with self.assertRaises(RecoveryValidationError):
            create_snapshot(str(self.source), str(self.snapshot))
        self.assertFalse(self.snapshot.exists())
        with sqlite3.connect(self.source) as db:
            db.execute("UPDATE sessions SET payload = ?", (json.dumps({"id": "different",
                "events": [], "config": {}}),))
        with self.assertRaises(RecoveryValidationError):
            create_snapshot(str(self.source), str(self.snapshot))
        self.assertFalse(self.snapshot.exists())

    def test_corrupt_and_missing_database_do_not_become_valid_backups(self):
        bad = self.root / "bad.sqlite3"
        bad.write_bytes(b"damaged database")
        with self.assertRaises(RecoveryValidationError):
            verify_snapshot(str(bad))
        with self.assertRaises(FileNotFoundError):
            verify_snapshot(str(self.root / "missing.sqlite3"))
