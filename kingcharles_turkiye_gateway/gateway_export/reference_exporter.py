#!/usr/bin/env python3
"""
REFERENCE ONLY.

Reads Türkiye aggregate SQLite tables and builds Aggregate Export v1 JSON.
This file contains NO network-send code and must not be treated as the live
production exporter until the live DB schema has been verified.

Real Türkiye -> Sydney export remains OFF.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


EVENT_NAMES_V2 = (
    "run_started",
    "upgrade_options_shown",
    "upgrade_selected",
    "run_checkpoint",
    "run_ended",
)


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row is not None


def rows_as_dicts(cursor: sqlite3.Cursor) -> list[dict]:
    columns = [description[0] for description in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def build_export(
    db_path: Path,
    bucket_date: str,
    revision: int,
    data_class: str = "SYNTHETIC_TEST",
) -> dict:
    with sqlite3.connect(db_path) as conn:
        event_counts = rows_as_dicts(
            conn.execute(
                """
                SELECT event_name, event_count AS count
                FROM event_counts
                WHERE bucket_date = ?
                  AND event_name IN (?, ?, ?, ?, ?)
                ORDER BY event_name
                """,
                (bucket_date, *EVENT_NAMES_V2),
            )
        )

        upgrade_option_counts = []
        if table_exists(conn, "upgrade_option_counts"):
            upgrade_option_counts = rows_as_dicts(
                conn.execute(
                    """
                    SELECT item_id, rarity, slot, shown_count
                    FROM upgrade_option_counts
                    WHERE bucket_date = ?
                    ORDER BY item_id, rarity, slot
                    """,
                    (bucket_date,),
                )
            )

        # The exact live selected-aggregate table name/columns must be verified
        # before deployment. If unavailable, the contract returns an empty list.
        upgrade_selected_counts = []
        if table_exists(conn, "upgrade_selected_counts"):
            upgrade_selected_counts = rows_as_dicts(
                conn.execute(
                    """
                    SELECT item_id, rarity, slot, selected_count
                    FROM upgrade_selected_counts
                    WHERE bucket_date = ?
                    ORDER BY item_id, rarity, slot
                    """,
                    (bucket_date,),
                )
            )

        run_checkpoint_counts = []
        if table_exists(conn, "run_checkpoint_counts"):
            run_checkpoint_counts = rows_as_dicts(
                conn.execute(
                    """
                    SELECT
                        checkpoint_number,
                        checkpoint_count,
                        player_level_sum,
                        current_xp_sum,
                        xp_to_next_level_sum,
                        hp_percent_sum,
                        total_kills_sum,
                        current_gold_sum
                    FROM run_checkpoint_counts
                    WHERE bucket_date = ?
                    ORDER BY checkpoint_number
                    """,
                    (bucket_date,),
                )
            )

        run_end_counts = []
        if table_exists(conn, "run_end_counts"):
            run_end_counts = rows_as_dicts(
                conn.execute(
                    """
                    SELECT
                        end_reason,
                        end_count,
                        run_duration_seconds_sum,
                        final_level_sum,
                        total_kills_sum,
                        current_gold_sum
                    FROM run_end_counts
                    WHERE bucket_date = ?
                    ORDER BY end_reason
                    """,
                    (bucket_date,),
                )
            )

    return {
        "schema_version": "aggregate-export-v1",
        "bucket_date": bucket_date,
        "revision": revision,
        "source_region": "TR",
        "destination_region": "ap-southeast-2",
        "privacy_mode": "aggregate_only",
        "data_class": data_class,
        "metrics": {
            "event_counts": event_counts,
            "upgrade_option_counts": upgrade_option_counts,
            "upgrade_selected_counts": upgrade_selected_counts,
            "run_checkpoint_counts": run_checkpoint_counts,
            "run_end_counts": run_end_counts,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("db")
    parser.add_argument("bucket_date")
    parser.add_argument("--revision", type=int, default=1)
    parser.add_argument("--output")
    parser.add_argument(
        "--data-class",
        choices=("SYNTHETIC_TEST", "PRIVACY_RELEASED_PROD_AGGREGATE"),
        default="SYNTHETIC_TEST",
    )
    args = parser.parse_args()

    payload = build_export(
        Path(args.db),
        args.bucket_date,
        args.revision,
        args.data_class,
    )
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"

    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        print(text, end="")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
