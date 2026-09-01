#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

from validate_export import validate_payload


DDL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS kc_exports (
    schema_version TEXT NOT NULL,
    bucket_date TEXT NOT NULL,
    revision INTEGER NOT NULL,
    source_region TEXT NOT NULL,
    destination_region TEXT NOT NULL,
    data_class TEXT NOT NULL,
    PRIMARY KEY (schema_version, bucket_date, revision, source_region)
);

CREATE TABLE IF NOT EXISTS kc_event_counts (
    schema_version TEXT NOT NULL,
    bucket_date TEXT NOT NULL,
    revision INTEGER NOT NULL,
    event_name TEXT NOT NULL,
    event_count INTEGER NOT NULL,
    PRIMARY KEY (schema_version, bucket_date, revision, event_name)
);

CREATE TABLE IF NOT EXISTS kc_upgrade_option_counts (
    schema_version TEXT NOT NULL,
    bucket_date TEXT NOT NULL,
    revision INTEGER NOT NULL,
    item_id TEXT NOT NULL,
    rarity TEXT NOT NULL,
    slot INTEGER NOT NULL,
    shown_count INTEGER NOT NULL,
    PRIMARY KEY (schema_version, bucket_date, revision, item_id, rarity, slot)
);

CREATE TABLE IF NOT EXISTS kc_upgrade_selected_counts (
    schema_version TEXT NOT NULL,
    bucket_date TEXT NOT NULL,
    revision INTEGER NOT NULL,
    item_id TEXT NOT NULL,
    rarity TEXT NOT NULL,
    slot INTEGER NOT NULL,
    selected_count INTEGER NOT NULL,
    PRIMARY KEY (schema_version, bucket_date, revision, item_id, rarity, slot)
);

CREATE TABLE IF NOT EXISTS kc_run_checkpoint_counts (
    schema_version TEXT NOT NULL,
    bucket_date TEXT NOT NULL,
    revision INTEGER NOT NULL,
    checkpoint_number INTEGER NOT NULL,
    checkpoint_count INTEGER NOT NULL,
    player_level_sum INTEGER NOT NULL,
    current_xp_sum REAL NOT NULL,
    xp_to_next_level_sum REAL NOT NULL,
    hp_percent_sum REAL NOT NULL,
    total_kills_sum INTEGER NOT NULL,
    current_gold_sum REAL NOT NULL,
    PRIMARY KEY (schema_version, bucket_date, revision, checkpoint_number)
);

CREATE TABLE IF NOT EXISTS kc_run_end_counts (
    schema_version TEXT NOT NULL,
    bucket_date TEXT NOT NULL,
    revision INTEGER NOT NULL,
    end_reason TEXT NOT NULL,
    end_count INTEGER NOT NULL,
    run_duration_seconds_sum REAL NOT NULL,
    final_level_sum INTEGER NOT NULL,
    total_kills_sum INTEGER NOT NULL,
    current_gold_sum REAL NOT NULL,
    PRIMARY KEY (schema_version, bucket_date, revision, end_reason)
);
"""


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def import_payload(payload: dict, db_path: Path) -> str:
    validate_payload(payload)

    schema_version = payload["schema_version"]
    bucket_date = payload["bucket_date"]
    revision = payload["revision"]
    source_region = payload["source_region"]
    destination_region = payload["destination_region"]
    data_class = payload["data_class"]
    metrics = payload["metrics"]

    with sqlite3.connect(db_path) as conn:
        conn.executescript(DDL)
        try:
            conn.execute(
                """
                INSERT INTO kc_exports (
                    schema_version, bucket_date, revision,
                    source_region, destination_region, data_class
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    schema_version, bucket_date, revision,
                    source_region, destination_region, data_class
                ),
            )
        except sqlite3.IntegrityError:
            return "DUPLICATE_IGNORED"

        conn.executemany(
            """
            INSERT INTO kc_event_counts
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    schema_version,
                    bucket_date,
                    revision,
                    row["event_name"],
                    row["count"],
                )
                for row in metrics["event_counts"]
            ],
        )

        conn.executemany(
            """
            INSERT INTO kc_upgrade_option_counts
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    schema_version,
                    bucket_date,
                    revision,
                    row["item_id"],
                    row["rarity"],
                    row["slot"],
                    row["shown_count"],
                )
                for row in metrics["upgrade_option_counts"]
            ],
        )

        conn.executemany(
            """
            INSERT INTO kc_upgrade_selected_counts
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    schema_version,
                    bucket_date,
                    revision,
                    row["item_id"],
                    row["rarity"],
                    row["slot"],
                    row["selected_count"],
                )
                for row in metrics["upgrade_selected_counts"]
            ],
        )

        conn.executemany(
            """
            INSERT INTO kc_run_checkpoint_counts
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    schema_version,
                    bucket_date,
                    revision,
                    row["checkpoint_number"],
                    row["checkpoint_count"],
                    row["player_level_sum"],
                    row["current_xp_sum"],
                    row["xp_to_next_level_sum"],
                    row["hp_percent_sum"],
                    row["total_kills_sum"],
                    row["current_gold_sum"],
                )
                for row in metrics["run_checkpoint_counts"]
            ],
        )

        conn.executemany(
            """
            INSERT INTO kc_run_end_counts
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    schema_version,
                    bucket_date,
                    revision,
                    row["end_reason"],
                    row["end_count"],
                    row["run_duration_seconds_sum"],
                    row["final_level_sum"],
                    row["total_kills_sum"],
                    row["current_gold_sum"],
                )
                for row in metrics["run_end_counts"]
            ],
        )

    return "IMPORTED"


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: import_to_sqlite.py <aggregate-export.json> <output.sqlite3>")
        return 2

    payload_path = Path(sys.argv[1]).resolve()
    db_path = Path(sys.argv[2]).resolve()
    payload = load_json(payload_path)
    result = import_payload(payload, db_path)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
