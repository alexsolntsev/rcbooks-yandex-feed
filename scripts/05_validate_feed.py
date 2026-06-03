from __future__ import annotations

import csv
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List

from common import ROOT, load_config, read_csv, write_csv


def count_offers(yml_path: Path) -> int:
    if not yml_path.exists():
        return 0
    try:
        root = ET.parse(yml_path).getroot()
        return len(root.findall(".//offer"))
    except ET.ParseError:
        return 0


def main() -> None:
    config = load_config()
    parsed = read_csv(ROOT / config["feed"]["parsed_file"])
    yml_path = ROOT / config["feed"]["output_file"]
    total = len(parsed)
    valid_rows = []
    errors: Dict[str, int] = {}
    ids = set()
    duplicate_ids = 0

    for b in parsed:
        row_errors = [e for e in (b.get("errors") or "").split(";") if e]
        for e in row_errors:
            errors[e] = errors.get(e, 0) + 1
        oid = b.get("offer_id", "")
        if oid in ids:
            duplicate_ids += 1
        ids.add(oid)
        if not any(e in row_errors for e in ["missing_title", "missing_price", "missing_image", "missing_url", "excluded_title_sapphires"]):
            valid_rows.append(b)

    offers = count_offers(yml_path)
    report = [
        {"metric": "parsed_rows", "value": total},
        {"metric": "valid_rows", "value": len(valid_rows)},
        {"metric": "offers_in_yml", "value": offers},
        {"metric": "duplicate_offer_ids", "value": duplicate_ids},
        {"metric": "new_books", "value": sum(1 for b in parsed if b.get("is_new") == "true")},
        {"metric": "popular_books", "value": sum(1 for b in parsed if b.get("is_popular") == "true")},
        {"metric": "cheap_books", "value": sum(1 for b in parsed if b.get("is_cheap") == "true")},
    ]
    for e, cnt in sorted(errors.items()):
        report.append({"metric": f"error_{e}", "value": cnt})
    write_csv(ROOT / config["feed"]["report_file"], report, ["metric", "value"])

    min_valid = int(config["feed"].get("min_valid_items", 10))
    if offers < min_valid:
        print(f"ERROR: only {offers} valid offers. Minimum is {min_valid}.")
        sys.exit(1)
    if duplicate_ids:
        print(f"ERROR: duplicate offer IDs found: {duplicate_ids}")
        sys.exit(1)
    print(f"Validation OK. Offers: {offers}. Report: {ROOT / config['feed']['report_file']}")


if __name__ == "__main__":
    main()
