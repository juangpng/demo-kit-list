# Supermicro Demo Kit Reservation System

Simple Streamlit web app to manage the demo systems inventory, reservations for events, and history tracking.

## Features

- **Inventory** – View all systems with filters (status, location, product family, search). Same core fields as the original Excel.
- **Reserve System(s)** – Select one or more available systems and assign them to an event with dates and notes.
- **Current Reservations** – See everything currently out. One-click “Mark as returned”.
- **History Tracker** – Searchable log of all past (and active) loans per system. You can also manually add historical records.
- **Manage Systems** – Add new units, edit existing ones, bulk status changes.
- **Events** – Helper list of known events.

Every physical unit has a unique **Asset ID** (DK-0001, DK-0002, …) so multiple units of the same SKU are tracked separately.

## Quick start

```bash
cd demo_kit_app

# (optional) create a virtualenv
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -r requirements.txt

# Database is already initialized with your current systems.
# If you ever need to recreate it:
# python init_db.py

streamlit run app.py
```

The app opens in your browser (usually http://localhost:8501).

## Data

- All data lives in `demo_kit.db` (SQLite) next to the app.
- History was started clean (as requested). Use the History page → “Add a past reservation manually” to back-fill old events when you have time.
- Current reservations were imported from the “Reserved = yes” rows in the original Excel.
- You can download the current inventory as CSV from the Inventory page at any time.

## Notes

- No internet required once packages are installed.
- You can later add extra fields (serial numbers, photos, cost, crates, etc.) – just let me know.
