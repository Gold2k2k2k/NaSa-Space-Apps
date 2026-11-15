"""The local handoff must be deterministic and omit private workspace material."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]


class TestJudgingPacket(unittest.TestCase):
    def test_tracked_source_snapshot_is_repeatable_and_excludes_secrets(self):
        self.assertTrue((ROOT / "scripts" / "package_submission.py").is_file(), "Local handoff builder is missing")
        from scripts import package_submission as packet
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, value in {"README.md": "local handoff", "app/main.py": "print('hello')\n", ".gitattributes": "app/data/* text eol=lf\n", ".env": "PRIVATE_TOKEN=secret",
                                ".superpowers/research.csv": "private cache", ".codex/settings.json": "private config",
                                "logs/run.log": "private log", "untracked.txt": "private scratch"}.items():
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(value.encode("utf-8"))
            subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
            subprocess.run(["git", "-c", f"safe.directory={root.as_posix()}", "-C", str(root), "add", "README.md", "app", ".gitattributes", ".env", ".superpowers", ".codex", "logs"], check=True, capture_output=True)
            # An unborn repository still has a reviewable staged source snapshot.
            with patch.object(packet, "ROOT", root):
                first = packet.package_submission(root / "first.zip")
                second = packet.package_submission(root / "second.zip")
            self.assertEqual((root / "first.zip").read_bytes(), (root / "second.zip").read_bytes())
            self.assertEqual(first["sha256"], second["sha256"])
            with zipfile.ZipFile(root / "first.zip") as archive:
                self.assertEqual(set(archive.namelist()), {"README.md", "app/main.py", ".gitattributes", "submission-manifest.json"})
                manifest = json.loads(archive.read("submission-manifest.json"))
                for name, digest in manifest["files"].items():
                    self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(), digest)
                self.assertEqual(manifest["files"]["app/main.py"], hashlib.sha256(b"print('hello')\n").hexdigest())


if __name__ == "__main__":
    unittest.main()
