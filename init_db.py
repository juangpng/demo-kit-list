#!/usr/bin/env python3
"""
Initialize the SQLite database for the Demo Kit Reservation System.
Imports systems from the cleaned JSON extracted from the original Excel.
History starts empty (user will re-enter later).
Current reservations are created from the existing 'Reserved' status.
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent / "demo_kit.db"
IMPORT_JSON = Path("/tmp/systems_import.json")

def create_schema(conn):
    cur = conn.cursor()

    # Systems inventory
    cur.execute("""
        CREATE TABLE IF NOT EXISTS systems (
            asset_id      TEXT PRIMARY KEY,
            product_family TEXT NOT NULL,
            sku           TEXT NOT NULL,
            code          TEXT,
            location      TEXT DEFAULT 'BV cage',
            notes         TEXT,
            status        TEXT DEFAULT 'Available' CHECK(status IN ('Available', 'Reserved', 'Maintenance', 'Scrapped')),
            created_at    TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at    TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Events (simple list for convenience)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL UNIQUE,
            partner       TEXT,
            start_date    TEXT,
            end_date      TEXT,
            notes         TEXT,
            created_at    TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Reservations + History (one table, status distinguishes active vs past)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reservations (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id      TEXT NOT NULL,
            event_name    TEXT NOT NULL,
            partner       TEXT,
            start_date    TEXT,
            end_date      TEXT,
            return_date   TEXT,
            notes         TEXT,
            status        TEXT DEFAULT 'active' CHECK(status IN ('active', 'returned', 'cancelled')),
            reserved_by   TEXT,
            created_at    TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at    TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (asset_id) REFERENCES systems(asset_id)
        )
    """)

    # Index for fast history lookups
    cur.execute("CREATE INDEX IF NOT EXISTS idx_res_asset ON reservations(asset_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_res_status ON reservations(status)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sys_status ON systems(status)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sys_sku ON systems(sku)")

    conn.commit()
    print("Schema created.")


def import_systems(conn):
    if not IMPORT_JSON.exists():
        print("WARNING: No import JSON found. Database will be empty.")
        return

    with open(IMPORT_JSON) as f:
        systems = json.load(f)

    cur = conn.cursor()
    imported = 0
    reserved_count = 0

    for s in systems:
        # Skip completely empty
        if not s.get("sku") and not s.get("product_family"):
            continue

        cur.execute("""
            INSERT OR REPLACE INTO systems
            (asset_id, product_family, sku, code, location, notes, status, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            s["asset_id"],
            s["product_family"] or "Unknown",
            s["sku"] or "Unknown",
            s.get("code") or "",
            s.get("location") or "BV cage",
            s.get("notes") or "",
            s.get("status") or "Available",
            datetime.now().isoformat(timespec="seconds")
        ))
        imported += 1

        # Create active reservation if currently reserved
        if s.get("status") == "Reserved" and s.get("initial_event"):
            event_name = s["initial_event"]
            # Try to parse dates roughly
            start_date = None
            end_date = None
            dates_str = s.get("initial_dates") or ""
            if dates_str:
                # Keep as free text for now; user can edit later
                pass

            cur.execute("""
                INSERT INTO reservations
                (asset_id, event_name, partner, start_date, end_date, return_date, notes, status, reserved_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?)
            """, (
                s["asset_id"],
                event_name,
                "",  # partner not separate in original
                None,
                None,
                s.get("initial_return") or None,
                f"Imported from Excel. Original dates field: {dates_str}" if dates_str else "Imported from Excel",
                "Imported"
            ))
            reserved_count += 1

    conn.commit()
    print(f"Imported {imported} systems.")
    print(f"Created {reserved_count} active reservations from existing data.")
    print("History table starts empty (as requested). You can add historical records later.")


def main():
    if DB_PATH.exists():
        print(f"Database already exists at {DB_PATH}. Deleting and recreating...")
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    create_schema(conn)
    import_systems(conn)
    conn.close()
    print(f"\nDatabase ready: {DB_PATH}")


if __name__ == "__main__":
    main()
