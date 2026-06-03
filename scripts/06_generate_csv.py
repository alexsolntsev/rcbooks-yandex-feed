from __future__ import annotations

import csv
import re
from typing import Any, Dict, List

from common import ROOT, clean_text, load_config, read_csv


BAD_TITLE_RE = re.compile(
    r"^\s*\d+\s+(?:сапфир(?:ов|а|ы)?|sapphire(?:s)?)\s*[-–—]\s*RC Books\s*$",
    re.IGNORECASE,
)


def short_text(value: str, limit: int) -> str:
    value = clean_text(value)
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)].rstrip() + "…"


def is_valid_image_url(url: str) -> bool:
    if not url:
        return False
    lower = clean_text(url).lower().split("?")[0]
    if any(token in lower for token in [
        "sapphire.svg",
        "svg-icons",
        "favicon",
        "logo",
        "placeholder",
        "data:image",
    ]):
        return False
    return lower.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))


def normalize_currency(value: str) -> str:
    value = clean_text(value).upper()
    if value in {"RUB", "RUR", "РУБ", "РУБ.", "₽"}:
        return "RUB"
    # Внутренние валюты магазина не передаём как Currency. Для Директа оставляем валидный ISO-код.
    return "RUB"


def normalize_price(value: str) -> str:
    value = clean_text(value).replace(",", ".")
    if not value:
        return ""
    try:
        number = float(value)
        return f"{number:.2f}"
    except ValueError:
        match = re.search(r"\d+(?:\.\d+)?", value)
        if not match:
            return ""
        number = float(match.group(0))
        return f"{number:.2f}"


def main() -> None:
    config = load_config()
    parsed_file = ROOT / config["feed"]["parsed_file"]
    output_file = ROOT / config["feed"].get("csv_output_file", "output/yandex-books.csv")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    books = read_csv(parsed_file)

    # В точности повторяем структуру универсального CSV из документации Яндекс Директа:
    # ID,ID2,Title,URL,Image,Description,Price,Old price,Currency
    # custom_label_* временно не добавляем, чтобы не мешать распознаванию фида/картинок.
    fieldnames = [
        "ID",
        "ID2",
        "Title",
        "URL",
        "Image",
        "Description",
        "Price",
        "Old price",
        "Currency",
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
        price = normalize_price(b.get("price", ""))
        old_price = normalize_price(b.get("old_price", ""))

        if old_price and price:
            try:
                if float(old_price) <= float(price):
                    old_price = ""
            except ValueError:
                old_price = ""

        if not url or not image or not is_valid_image_url(image) or not price:
            continue

        rows.append({
            "ID": offer_id,
            # ID2 оставляем пустым. Это сохраняет совместимость с примером Яндекса,
            # но не меняет основной ID оффера для будущего ecommerce-сопоставления.
            "ID2": "",
            "Title": short_text(title, 120),
            "URL": url,
            "Image": image,
            "Description": short_text(b.get("description", ""), 500),
            "Price": price,
            "Old price": old_price,
            "Currency": normalize_currency(b.get("currency", "RUB")),
        })

    # Без BOM, обычный UTF-8, как в примере из документации.
    with open(output_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated {output_file} with {len(rows)} rows")


if __name__ == "__main__":
    main()
