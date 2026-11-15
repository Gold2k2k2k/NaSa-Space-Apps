# FireTrace judging packet

Start with the [English submission](submission.md), [seven-slide outline](slides.md),
[Vietnamese team notes](team-notes-vi.md) and [evidence and limits](evidence.md).
The slide count is our internal format, not a verified 2026 limit.

Run locally with Python 3.11 after installing `requirements.txt`:

```powershell
python run.py
```

Open localhost:8000 and choose **Explore NASA FIRMS case**. The existing opening
screen remains a clearly labeled generated example. The actual case is separate.
Use **Review periods**, switch raw/harmonized, inspect the training/held-out
assessment in Sensor Bridge, and open **Carry the evidence** for the manager
brief and receipt/audit downloads. Missing observations stay unknown.

For a repeatable case without the browser:

```powershell
python run.py --case-study central-highlands --output logs/case.json --receipt logs/case-receipt.json --package logs/case-audit.zip
python -S -B verify.py logs/case-receipt.json
python scripts/package_submission.py --output logs/firetrace-submission.zip
```

Create `logs` first for CLI output. Extracted audit ZIPs include `verify.py` and its
standard-library modules; verification needs no third-party packages. Analysis
replay needs the declared application dependencies. The submission ZIP is a
local source/evidence handoff, not an upload. Its manifest lists file hashes.

The repository was private when reviewed. Public links, actual submission,
repository visibility and deployment remain owner-controlled steps. Confirm the
current challenge's format and accessibility requirements before submitting.
