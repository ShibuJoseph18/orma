#!/usr/bin/env python3
"""Inspect an exported Linkosh SQLite database locally, without modifying it."""
import argparse
import csv
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

FIELDS = (
    "id", "provider", "account", "external_id", "url", "title", "summary",
    "poster_name", "poster_handle", "poster_bio", "image", "kind", "duration",
    "collection", "bookmarked_at", "published_at", "created_at",
)

def inspect(database, output_root, sample_size=20):
    database = Path(database).expanduser().resolve(strict=True)
    connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only = ON")
        connection.execute("PRAGMA trusted_schema = OFF")
        tables = {r[0] for r in connection.execute(
            "SELECT name FROM sqlite_schema WHERE type = 'table'")}
        if "saved_items" not in tables:
            raise ValueError("This database has no saved_items table. Export the Linkosh database.")
        columns = {r[1] for r in connection.execute("PRAGMA table_info(saved_items)")}
        if "provider" not in columns:
            raise ValueError("The saved_items table has no provider column.")
        fields = [f for f in FIELDS if f in columns]
        where = "provider = 'linkedin'"
        if "deleted_at" in columns:
            where += " AND deleted_at IS NULL"
        order = " ORDER BY id DESC" if "id" in columns else ""
        rows = [dict(r) for r in connection.execute(
            "SELECT " + ", ".join(fields) + " FROM saved_items WHERE " + where + order)]
        coverage = {
            field: sum(row.get(field) is not None and str(row.get(field)).strip() not in ("", "[]", "{}")
                       for row in rows)
            for field in fields
        }
        lengths = [len(row.get("summary") or "") for row in rows]
        raw = []
        if "raw_data" in tables:
            raw_columns = {r[1] for r in connection.execute("PRAGMA table_info(raw_data)")}
            if {"provider", "kind", "status", "body"} <= raw_columns:
                raw = [dict(r) for r in connection.execute(
                    "SELECT kind, status, COUNT(*) AS pages, SUM(length(body)) AS body_characters "
                    "FROM raw_data WHERE provider = 'linkedin' GROUP BY kind, status")]
    finally:
        connection.close()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = Path(output_root).resolve() / (database.stem + "-" + stamp)
    output.mkdir(parents=True, mode=0o700)
    samples = rows[:sample_size]
    summary = {
        "input_database": str(database),
        "database_sha256": hashlib.sha256(database.read_bytes()).hexdigest(),
        "linkedin_items": len(rows),
        "available_columns": sorted(columns),
        "populated_field_counts": coverage,
        "summary_text_characters": {
            "minimum": min(lengths, default=0),
            "maximum": max(lengths, default=0),
            "total": sum(lengths),
        },
        "raw_response_pages": raw,
        "note": "Text length and an ellipsis cannot establish completeness; compare with original posts.",
    }
    (output / "coverage.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (output / "sample-posts.json").write_text(
        json.dumps(samples, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (output / "compare-with-linkedin.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("url", "author", "text_characters", "manual_format",
                         "full_text_matches_original", "all_media_present", "notes"))
        for row in samples:
            writer.writerow((row.get("url", ""), row.get("poster_name", ""),
                             len(row.get("summary") or ""), "", "", "", ""))
    return summary, output

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    parser.add_argument("--sample", type=int, default=20)
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "reports")
    args = parser.parse_args()
    if args.sample < 1:
        parser.error("--sample must be at least 1")
    try:
        summary, output = inspect(args.database, args.out, args.sample)
    except (OSError, sqlite3.Error, ValueError) as error:
        parser.exit(1, "Inspection failed: " + str(error) + "\n")
    print("LinkedIn items:", summary["linkedin_items"])
    print("Raw response pages:", sum(r["pages"] for r in summary["raw_response_pages"]))
    print("Report folder:", output)
    print("The exported database was opened read-only. No network requests were made.")

if __name__ == "__main__":
    main()
