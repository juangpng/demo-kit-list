#!/usr/bin/env python3
"""
Supermicro Demo Kit Reservation System
Streamlit web app for inventory, reservations, and history tracking.
"""

import streamlit as st
import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime, date
from contextlib import contextmanager

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DB_PATH = Path(__file__).parent / "demo_kit.db"
st.set_page_config(
    page_title="Demo Kit Manager",
    page_icon="🖥️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def query_df(sql, params=None):
    with get_conn() as conn:
        return pd.read_sql_query(sql, conn, params=params or [])


def execute(sql, params=None):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql, params or [])
        conn.commit()
        return cur.lastrowid


def execute_many(sql, params_list):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.executemany(sql, params_list)
        conn.commit()


# ---------------------------------------------------------------------------
# Ensure DB exists
# ---------------------------------------------------------------------------
if not DB_PATH.exists():
    st.error("Database not found. Please run `python init_db.py` first.")
    st.stop()


# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------
st.sidebar.title("🖥️ Demo Kit Manager")
st.sidebar.markdown("Supermicro systems reservation & history")

page = st.sidebar.radio(
    "Navigation",
    [
        "📊 Inventory",
        "📅 Reserve System(s)",
        "🔴 Current Reservations",
        "📜 History Tracker",
        "➕ Manage Systems",
        "📋 Events",
    ],
)

st.sidebar.markdown("---")
st.sidebar.caption("Data is stored locally in SQLite.\nExport anytime from Inventory.")


# ---------------------------------------------------------------------------
# PAGE: Inventory
# ---------------------------------------------------------------------------
if page == "📊 Inventory":
    st.header("Systems Inventory")

    # Filters
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        status_filter = st.multiselect(
            "Status",
            ["Available", "Reserved", "Maintenance", "Scrapped"],
            default=["Available"],
        )
    with col2:
        locations = query_df("SELECT DISTINCT location FROM systems ORDER BY location")["location"].tolist()
        loc_filter = st.multiselect("Location", locations, default=[])
    with col3:
        families = query_df("SELECT DISTINCT product_family FROM systems ORDER BY product_family")["product_family"].tolist()
        fam_filter = st.multiselect("Product Family", families)
    with col4:
        search = st.text_input("Search SKU / Asset ID / Notes", "")

    # Build query
    sql = "SELECT * FROM systems WHERE 1=1"
    params = []
    if status_filter:
        sql += f" AND status IN ({','.join('?'*len(status_filter))})"
        params.extend(status_filter)
    if loc_filter:
        sql += f" AND location IN ({','.join('?'*len(loc_filter))})"
        params.extend(loc_filter)
    if fam_filter:
        sql += f" AND product_family IN ({','.join('?'*len(fam_filter))})"
        params.extend(fam_filter)
    if search:
        sql += " AND (sku LIKE ? OR asset_id LIKE ? OR notes LIKE ? OR product_family LIKE ?)"
        q = f"%{search}%"
        params.extend([q, q, q, q])
    sql += " ORDER BY product_family, sku, asset_id"

    df = query_df(sql, params)

    # Summary metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total shown", len(df))
    m2.metric("Available", (df["status"] == "Available").sum() if len(df) else 0)
    m3.metric("Reserved", (df["status"] == "Reserved").sum() if len(df) else 0)
    m4.metric("Other", ((df["status"] != "Available") & (df["status"] != "Reserved")).sum() if len(df) else 0)

    st.dataframe(
        df[["asset_id", "product_family", "sku", "code", "location", "status", "notes"]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "asset_id": "Asset ID",
            "product_family": "Product Family",
            "sku": "SKU",
            "code": "Code",
            "location": "Location",
            "status": st.column_config.TextColumn("Status"),
            "notes": "Notes",
        },
    )

    # Export
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Download current view as CSV",
        csv,
        "demo_kit_inventory.csv",
        "text/csv",
    )


# ---------------------------------------------------------------------------
# PAGE: Reserve System(s)
# ---------------------------------------------------------------------------
elif page == "📅 Reserve System(s)":
    st.header("Reserve System(s) for an Event")

    # Available systems
    avail = query_df(
        "SELECT asset_id, product_family, sku, location, notes FROM systems WHERE status = 'Available' ORDER BY product_family, sku"
    )

    if avail.empty:
        st.warning("No available systems right now.")
    else:
        st.subheader("1. Select systems")
        # Multi-select with nice labels
        options = {
            f"{r['asset_id']} | {r['product_family']} | {r['sku']} ({r['location']})": r["asset_id"]
            for _, r in avail.iterrows()
        }
        selected_labels = st.multiselect(
            "Available systems",
            list(options.keys()),
            help="You can select multiple systems for the same event",
        )
        selected_ids = [options[l] for l in selected_labels]

        st.subheader("2. Event details")
        c1, c2 = st.columns(2)
        with c1:
            event_name = st.text_input("Event / Partner name *", placeholder="e.g. ISC 2026 – ASBIS booth")
            partner = st.text_input("Partner / Booth / Contact (optional)")
            reserved_by = st.text_input("Reserved by", placeholder="Your name")
        with c2:
            start_date = st.date_input("Event start date", value=None)
            end_date = st.date_input("Event end date", value=None)
            return_date = st.date_input("Expected return date to BV", value=None)

        notes = st.text_area("Notes", placeholder="Any special instructions, shipping, etc.")

        if st.button("✅ Confirm Reservation", type="primary", disabled=not selected_ids or not event_name):
            now = datetime.now().isoformat(timespec="seconds")
            for aid in selected_ids:
                # Insert reservation
                execute(
                    """
                    INSERT INTO reservations
                    (asset_id, event_name, partner, start_date, end_date, return_date, notes, status, reserved_by, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
                    """,
                    (
                        aid,
                        event_name,
                        partner or None,
                        start_date.isoformat() if start_date else None,
                        end_date.isoformat() if end_date else None,
                        return_date.isoformat() if return_date else None,
                        notes or None,
                        reserved_by or None,
                        now,
                        now,
                    ),
                )
                # Update system status
                execute(
                    "UPDATE systems SET status = 'Reserved', updated_at = ? WHERE asset_id = ?",
                    (now, aid),
                )
            st.success(f"Reserved {len(selected_ids)} system(s) for **{event_name}**")
            st.balloons()
            st.rerun()


# ---------------------------------------------------------------------------
# PAGE: Current Reservations
# ---------------------------------------------------------------------------
elif page == "🔴 Current Reservations":
    st.header("Current Active Reservations")

    df = query_df(
        """
        SELECT r.id, r.asset_id, s.product_family, s.sku, s.location,
               r.event_name, r.partner, r.start_date, r.end_date, r.return_date,
               r.notes, r.reserved_by, r.created_at
        FROM reservations r
        JOIN systems s ON s.asset_id = r.asset_id
        WHERE r.status = 'active'
        ORDER BY r.event_name, s.product_family
        """
    )

    if df.empty:
        st.info("No active reservations.")
    else:
        st.metric("Active reservations", len(df))

        # Group by event for nicer display
        for event, group in df.groupby("event_name"):
            with st.expander(f"**{event}**  ({len(group)} system(s))", expanded=True):
                st.dataframe(
                    group[
                        [
                            "asset_id",
                            "product_family",
                            "sku",
                            "location",
                            "partner",
                            "start_date",
                            "end_date",
                            "return_date",
                            "reserved_by",
                            "notes",
                        ]
                    ],
                    use_container_width=True,
                    hide_index=True,
                )

                # Return buttons
                st.markdown("**Mark as returned:**")
                cols = st.columns(min(4, len(group)))
                for idx, (_, row) in enumerate(group.iterrows()):
                    with cols[idx % len(cols)]:
                        if st.button(
                            f"↩️ {row['asset_id']}",
                            key=f"return_{row['id']}",
                            help=f"Return {row['sku']}",
                        ):
                            now = datetime.now().isoformat(timespec="seconds")
                            execute(
                                """
                                UPDATE reservations
                                SET status = 'returned', return_date = COALESCE(return_date, ?), updated_at = ?
                                WHERE id = ?
                                """,
                                (date.today().isoformat(), now, row["id"]),
                            )
                            execute(
                                "UPDATE systems SET status = 'Available', updated_at = ? WHERE asset_id = ?",
                                (now, row["asset_id"]),
                            )
                            st.success(f"{row['asset_id']} marked as returned and now Available")
                            st.rerun()


# ---------------------------------------------------------------------------
# PAGE: History Tracker
# ---------------------------------------------------------------------------
elif page == "📜 History Tracker":
    st.header("History Tracker – Where systems have been used")

    # Filters
    c1, c2, c3 = st.columns(3)
    with c1:
        asset_search = st.text_input("Filter by Asset ID or SKU")
    with c2:
        event_search = st.text_input("Filter by Event name")
    with c3:
        status_hist = st.multiselect(
            "Reservation status",
            ["active", "returned", "cancelled"],
            default=["returned", "active"],
        )

    sql = """
        SELECT r.id, r.asset_id, s.product_family, s.sku, s.location,
               r.event_name, r.partner, r.start_date, r.end_date, r.return_date,
               r.notes, r.reserved_by, r.status, r.created_at
        FROM reservations r
        JOIN systems s ON s.asset_id = r.asset_id
        WHERE 1=1
    """
    params = []
    if asset_search:
        sql += " AND (r.asset_id LIKE ? OR s.sku LIKE ?)"
        q = f"%{asset_search}%"
        params.extend([q, q])
    if event_search:
        sql += " AND r.event_name LIKE ?"
        params.append(f"%{event_search}%")
    if status_hist:
        sql += f" AND r.status IN ({','.join('?'*len(status_hist))})"
        params.extend(status_hist)
    sql += " ORDER BY r.created_at DESC"

    df = query_df(sql, params)

    st.caption(f"{len(df)} record(s) found")
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "asset_id": "Asset ID",
            "product_family": "Product Family",
            "event_name": "Event",
            "status": "Status",
        },
    )

    # Quick view history for one system
    st.subheader("Quick history for one system")
    all_assets = query_df(
        "SELECT asset_id || ' | ' || product_family || ' | ' || sku AS label, asset_id FROM systems ORDER BY product_family"
    )
    if not all_assets.empty:
        choice = st.selectbox("Select system", all_assets["label"].tolist())
        if choice:
            aid = all_assets.loc[all_assets["label"] == choice, "asset_id"].iloc[0]
            hist = query_df(
                """
                SELECT event_name, partner, start_date, end_date, return_date, status, notes, reserved_by, created_at
                FROM reservations
                WHERE asset_id = ?
                ORDER BY created_at DESC
                """,
                [aid],
            )
            if hist.empty:
                st.info("No reservation history yet for this system. (You can add past records below or via Manage.)")
            else:
                st.dataframe(hist, use_container_width=True, hide_index=True)

    # Manual add historical record
    with st.expander("➕ Add a past (historical) reservation manually"):
        st.markdown("Use this to back-fill history for systems.")
        h_assets = query_df("SELECT asset_id, product_family, sku FROM systems ORDER BY product_family, sku")
        h_options = {
            f"{r['asset_id']} | {r['product_family']} | {r['sku']}": r["asset_id"]
            for _, r in h_assets.iterrows()
        }
        h_sel = st.selectbox("System", list(h_options.keys()), key="hist_sys")
        h_event = st.text_input("Event name", key="hist_event")
        h_partner = st.text_input("Partner", key="hist_partner")
        hc1, hc2, hc3 = st.columns(3)
        with hc1:
            h_start = st.date_input("Start", value=None, key="hist_start")
        with hc2:
            h_end = st.date_input("End", value=None, key="hist_end")
        with hc3:
            h_return = st.date_input("Returned", value=None, key="hist_return")
        h_notes = st.text_area("Notes", key="hist_notes")
        if st.button("Add historical record") and h_sel and h_event:
            execute(
                """
                INSERT INTO reservations
                (asset_id, event_name, partner, start_date, end_date, return_date, notes, status, reserved_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'returned', 'Manual history entry')
                """,
                (
                    h_options[h_sel],
                    h_event,
                    h_partner or None,
                    h_start.isoformat() if h_start else None,
                    h_end.isoformat() if h_end else None,
                    h_return.isoformat() if h_return else None,
                    h_notes or None,
                ),
            )
            st.success("Historical record added.")
            st.rerun()


# ---------------------------------------------------------------------------
# PAGE: Manage Systems
# ---------------------------------------------------------------------------
elif page == "➕ Manage Systems":
    st.header("Manage Systems")

    tab1, tab2, tab3 = st.tabs(["Add new system", "Edit existing", "Bulk status change"])

    with tab1:
        st.subheader("Add a new system")
        with st.form("add_system"):
            ac1, ac2 = st.columns(2)
            with ac1:
                new_family = st.text_input("Product Family *")
                new_sku = st.text_input("SKU *")
                new_code = st.text_input("Code (e.g. H14, Grace)")
            with ac2:
                new_loc = st.text_input("Location", value="BV cage")
                new_notes = st.text_area("Notes")
                new_status = st.selectbox("Status", ["Available", "Reserved", "Maintenance", "Scrapped"])

            if st.form_submit_button("Add system"):
                if new_family and new_sku:
                    # Generate next asset_id
                    last = query_df("SELECT asset_id FROM systems ORDER BY asset_id DESC LIMIT 1")
                    if last.empty:
                        next_id = "DK-0001"
                    else:
                        num = int(last.iloc[0]["asset_id"].split("-")[1]) + 1
                        next_id = f"DK-{num:04d}"
                    execute(
                        """
                        INSERT INTO systems (asset_id, product_family, sku, code, location, notes, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (next_id, new_family, new_sku, new_code or "", new_loc, new_notes or "", new_status),
                    )
                    st.success(f"Added {next_id}")
                    st.rerun()
                else:
                    st.error("Product Family and SKU are required.")

    with tab2:
        st.subheader("Edit an existing system")
        all_sys = query_df("SELECT asset_id, product_family, sku FROM systems ORDER BY product_family, sku")
        if all_sys.empty:
            st.info("No systems yet.")
        else:
            edit_options = {
                f"{r['asset_id']} | {r['product_family']} | {r['sku']}": r["asset_id"]
                for _, r in all_sys.iterrows()
            }
            edit_sel = st.selectbox("Select system to edit", list(edit_options.keys()))
            if edit_sel:
                aid = edit_options[edit_sel]
                current = query_df("SELECT * FROM systems WHERE asset_id = ?", [aid]).iloc[0]

                with st.form("edit_system"):
                    ec1, ec2 = st.columns(2)
                    with ec1:
                        e_family = st.text_input("Product Family", value=current["product_family"])
                        e_sku = st.text_input("SKU", value=current["sku"])
                        e_code = st.text_input("Code", value=current["code"] or "")
                    with ec2:
                        e_loc = st.text_input("Location", value=current["location"])
                        e_notes = st.text_area("Notes", value=current["notes"] or "")
                        e_status = st.selectbox(
                            "Status",
                            ["Available", "Reserved", "Maintenance", "Scrapped"],
                            index=["Available", "Reserved", "Maintenance", "Scrapped"].index(current["status"]),
                        )

                    if st.form_submit_button("Save changes"):
                        now = datetime.now().isoformat(timespec="seconds")
                        execute(
                            """
                            UPDATE systems
                            SET product_family=?, sku=?, code=?, location=?, notes=?, status=?, updated_at=?
                            WHERE asset_id=?
                            """,
                            (e_family, e_sku, e_code, e_loc, e_notes, e_status, now, aid),
                        )
                        st.success("Updated.")
                        st.rerun()

    with tab3:
        st.subheader("Bulk change status")
        st.warning("Use carefully. This does not create/close reservations automatically.")
        bulk_status = st.selectbox("New status", ["Available", "Reserved", "Maintenance", "Scrapped"], key="bulk")
        bulk_ids = st.text_area("Asset IDs (one per line)", placeholder="DK-0001\nDK-0002")
        if st.button("Apply bulk status"):
            ids = [x.strip() for x in bulk_ids.splitlines() if x.strip()]
            if ids:
                now = datetime.now().isoformat(timespec="seconds")
                for aid in ids:
                    execute(
                        "UPDATE systems SET status=?, updated_at=? WHERE asset_id=?",
                        (bulk_status, now, aid),
                    )
                st.success(f"Updated {len(ids)} systems to {bulk_status}")
                st.rerun()


# ---------------------------------------------------------------------------
# PAGE: Events
# ---------------------------------------------------------------------------
elif page == "📋 Events":
    st.header("Events")

    st.markdown(
        "This is a simple helper list of known events. "
        "Reservations store the event name as free text, so you don't have to pre-create events."
    )

    # List existing from reservations
    events_from_res = query_df(
        """
        SELECT event_name, COUNT(*) as times_used,
               MIN(start_date) as earliest, MAX(end_date) as latest
        FROM reservations
        GROUP BY event_name
        ORDER BY times_used DESC
        """
    )
    if not events_from_res.empty:
        st.subheader("Events seen in reservations")
        st.dataframe(events_from_res, use_container_width=True, hide_index=True)

    # Manual events table
    with st.expander("Manage named events (optional)"):
        named = query_df("SELECT * FROM events ORDER BY name")
        if not named.empty:
            st.dataframe(named, use_container_width=True, hide_index=True)

        with st.form("add_event"):
            ev_name = st.text_input("Event name")
            ev_partner = st.text_input("Partner")
            ec1, ec2 = st.columns(2)
            with ec1:
                ev_start = st.date_input("Start", value=None, key="ev_start")
            with ec2:
                ev_end = st.date_input("End", value=None, key="ev_end")
            ev_notes = st.text_area("Notes")
            if st.form_submit_button("Add event"):
                if ev_name:
                    try:
                        execute(
                            """
                            INSERT INTO events (name, partner, start_date, end_date, notes)
                            VALUES (?, ?, ?, ?, ?)
                            """,
                            (
                                ev_name,
                                ev_partner or None,
                                ev_start.isoformat() if ev_start else None,
                                ev_end.isoformat() if ev_end else None,
                                ev_notes or None,
                            ),
                        )
                        st.success("Event added.")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("Event name already exists.")
