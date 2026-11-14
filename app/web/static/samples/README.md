# Synthetic upload examples

These files are **invented test data**, not NASA observations or real events.
They use FIRMS-compatible column names to demonstrate uploads and missing data.
The application correctly labels them as uploaded CSVs and leaves their source
authentication unestablished.

- `generated-firms-demo.csv`: 12 valid rows, mixed MODIS/VIIRS fields, supplied
  thermal-source types, measured-zero/missing FRP and a missing acquisition time.
- `generated-mixed-quality.csv`: 3 valid rows and 2 deliberately invalid rows
  (an impossible date and a nonnumeric latitude), demonstrating rejection counts.

Both are short detection-only archives. Missing months are unknown and the
verdict is UNVERIFIABLE; they must not acquire a 2001–2020 reference history.
Regenerate with `python scripts/generate_examples.py` from the repository root.
