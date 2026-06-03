from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any, Dict, List

from common import ROOT, clean_text, load_config, read_csv


def trim(text: str, limit: int) -> str:
    text = clean_text(text)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def clean_price(value: str) -> str:
    text = clean_text(value)
    match = re.search(r"\d+(?:[.,]\d+)?", text)
    if not match:
        return ""
    number = match.group(0).replace(",", ".")
    try:
        return str(int(round(float(number))))
    except ValueError:
        return ""


def is_valid_image(url: str) -> bool:
    u = clean_text(url).lower().split("?")[0]
    return u.startswith(("http://", "https://")) and u.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))


def main() -> None:
    config = load_config()
    parsed_file = ROOT / config["feed"]["parsed_file"]
    out_file = ROOT / "output" / "yandex-books-catalog.csv"
    out_file.parent.mkdir(parents=True, exist_ok=True)

    books = read_csv(parsed_file)

    # Это CSV не для универсального фида товаров, а для CSV-файла страниц каталога,
    # где Директ ждёт Image url 1, а не Image.
    fieldnames = [
        "Url",
        "Title",
        "Description",
        "Offer minimal price",
        "Currency",
        "Image url 1",
        "Image url 2",
        "Image url 3",
        "Image url 4",
        "Image url 5",
    ]

    rows: List[Dict[str, Any]] = []
    seen_urls = set()
    for b in books:
        url = clean_text(b.get("url", ""))
        image_url = clean_text(b.get("image_url", ""))
        title = clean_text(b.get("title", ""))
        price = clean_price(b.get("price", ""))

        if not url or url in seen_urls:
            continue
        if not title or not price or not is_valid_image(image_url):
            continue
        if b.get("errors") and any(e in b["errors"] for e in ["missing_title", "missing_price", "missing_image", "excluded_title"]):
            continue

        seen_urls.add(url)
        rows.append({
            "Url": url,
            "Title": trim(title, 56),
            "Description": trim(b.get("description", ""), 81),
            "Offer minimal price": price,
            "Currency": "RUB",
            "Image url 1": image_url,
            "Image url 2": "",
            "Image url 3": "",
            "Image url 4": "",
            "Image url 5": "",
        })

    with out_file.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=",")
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated catalog CSV: {out_file} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
