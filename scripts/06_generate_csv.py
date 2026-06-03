from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any, Dict, List

from common import ROOT, clean_text, load_config, read_csv


BAD_TITLE_RE = re.compile(r"^\s*\d+\s+(?:сапфир(?:ов|а|ы)?|sapphire(?:s)?)\s*[-–—]\s*RC Books\s*$", re.IGNORECASE)


def short_text(value: str, limit: int) -> str:
    value = clean_text(value)
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)].rstrip() + "…"


def is_valid_image_url(url: str) -> bool:
    if not url:
        return False
    lower = url.lower().split("?")[0]
    if any(token in lower for token in ["sapphire.svg", "svg-icons", "favicon", "logo", "placeholder", "data:image"]):
        return False
    return lower.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))


def normalize_currency(value: str) -> str:
    value = clean_text(value).upper()
    # Для Директа используем валидную валюту. Сапфиры передаём отдельными custom_label/параметрами.
    if value in {"RUB", "RUR", "РУБ", "РУБ.", "₽"}:
        return "RUB"
    return "RUB"


def main() -> None:
    config = load_config()
    parsed_file = ROOT / config["feed"]["parsed_file"]
    output_file = ROOT / config["feed"].get("csv_output_file", "output/yandex-books.csv")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    books = read_csv(parsed_file)

    # Universal CSV feed for Yandex Direct / EPK.
    # Official fields: ID, URL, Image, Title, Description, Price, Currency,
    # custom_label_0..4, custom_score.
    fieldnames = [
        "ID",
        "URL",
        "Image",
        "Title",
        "Description",
        "Price",
        "Currency",
        "Old Price",
        "custom_label_0",
        "custom_label_1",
        "custom_label_2",
        "custom_label_3",
        "custom_label_4",
        "custom_score",
    ]

    rows: List[Dict[str, Any]] = []
    seen_ids = set()

    for b in books:
        title = clean_text(b.get("title", ""))
        if not title or BAD_TITLE_RE.match(title):
            continue

        offer_id = clean_text(b.get("offer_id", ""))[:100]
        if not offer_id or offer_id in seen_ids:
            continue
        seen_ids.add(offer_id)

        url = clean_text(b.get("url", ""))
        image = clean_text(b.get("image_url", ""))
        price = clean_text(b.get("price", ""))

        if not url or not image or not is_valid_image_url(image) or not price:
            continue

        internal_currency = clean_text(b.get("internal_currency", ""))
        # Если поле не заведено, считаем цену сапфировой, когда она пришла не из RUB override.
        if not internal_currency and normalize_currency(b.get("currency", "RUB")) == "RUB":
            internal_currency = clean_text(b.get("currency", "RUB"))

        rows.append({
            "ID": offer_id,
            "URL": url,
            "Image": image,
            "Title": short_text(title, 120),
            "Description": short_text(b.get("description", ""), 500),
            "Price": price,
            "Currency": "RUB",
            "Old Price": clean_text(b.get("old_price", "")),
            # Use labels for filters in EPK. They do not affect creative generation.
            "custom_label_0": clean_text(b.get("feed_group", "default")),
            "custom_label_1": internal_currency or "RUB",
            "custom_label_2": "is_new" if b.get("is_new") == "true" else "",
            "custom_label_3": "is_popular" if b.get("is_popular") == "true" else "",
            "custom_label_4": "is_cheap" if b.get("is_cheap") == "true" else "",
            "custom_score": clean_text(b.get("priority", "50")) or "50",
        })

    with open(output_file, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated {output_file} with {len(rows)} rows")


if __name__ == "__main__":
    main()
