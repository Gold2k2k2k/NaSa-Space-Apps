"""Create a deterministic local source/evidence handoff; never publishes anything."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def package_submission(output: Path) -> dict:
    root = ROOT.resolve()
    command = ["git", "-c", f"safe.directory={root.as_posix()}", "-C", str(root)]
    tracked = subprocess.check_output([*command, "ls-files", "--cached", "-z"]).decode("utf-8").split("\0")
    revision = subprocess.run([*command, "rev-parse", "--verify", "HEAD"], capture_output=True, text=True)
    members = {}
    forbidden = {"logs", "__pycache__", "venv", "node_modules", ".git", ".codex", ".agents", ".aws", ".superpowers", ".codegraph", ".venv"}
    for name in sorted(set(tracked) - {""}):
        path = PurePosixPath(name)
        if (path.is_absolute() or ".." in path.parts or any(p in forbidden for p in path.parts)
                or any(p.startswith(".") and p not in {".gitignore", ".dockerignore", ".env.example"} for p in path.parts)
                or path.suffix.lower() in {".pem", ".key", ".p12", ".pfx", ".log", ".pyc"}):
            continue
        source = root.joinpath(*path.parts)
        if source.is_symlink() or root not in source.resolve().parents:
            raise ValueError(f"Source is outside the handoff root: {name}")
        members[name] = source.read_bytes()
    destination = Path(output).resolve()
    if destination.suffix.lower() != ".zip" or destination in {root / name for name in members}:
        raise ValueError("Choose an untracked .zip output path")
    manifest = {"format": "firetrace-local-handoff-v1", "source_revision": revision.stdout.strip() if revision.returncode == 0 else "uncommitted",
                "scope": "Tracked source and evidence at packaging time; unsigned file hashes; no deployment or publication.",
                "files": {name: hashlib.sha256(content).hexdigest() for name, content in members.items()}}
    members["submission-manifest.json"] = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode("utf-8")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, payload in sorted(members.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, payload, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    payload = buffer.getvalue()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)
    return {"path": str(destination), "files": len(members), "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "logs" / "firetrace-submission.zip")
    print(json.dumps(package_submission(parser.parse_args().output), indent=2))
