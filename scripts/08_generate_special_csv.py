from __future__ import annotations

import csv
import re
from typing import Any, Dict, List

from common import ROOT, clean_text, load_config, read_csv


BAD_TITLE_RE = re.compile(
    r"^\s*\d+\s+(?:сапфир(?:ов|а|ы)?|sapphire(?:s)?)\s*[-–—]\s*RC Books\s*$",
    re.IGNORECASE,
)


def trim(value: str, limit: int) -> str:
    value = clean_text(value)
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)].rstrip() + "…"


def clean_price(value: str) -> str:
    text = clean_text(value)
    match = re.search(r"\d+(?:[.,]\d+)?", text)
    if not match:
        return ""
    number = match.group(0).replace(",", ".")
    try:
        val = float(number)
        if val <= 0:
            return ""
        if val.is_integer():
            return str(int(val))
        return f"{val:.2f}"
    except ValueError:
        return ""


def price_with_currency(price: str, currency: str = "RUB") -> str:
    price = clean_price(price)
    if not price:
        return ""
    currency = clean_text(currency).upper() or "RUB"
    if currency not in {"RUB", "USD", "UAH", "KZT"}:
        currency = "RUB"
    return f"{price} {currency}"


def is_valid_image(url: str) -> bool:
    if not url:
        return False
    u = clean_text(url).lower().split("?")[0]
    if not u.startswith(("http://", "https://")):
        return False
    if any(token in u for token in ["sapphire.svg", "svg-icons", "favicon", "logo", "placeholder", "data:image"]):
        return False
    return u.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))


def is_excluded(book: Dict[str, str]) -> bool:
    title = clean_text(book.get("title", ""))
    if not title or BAD_TITLE_RE.match(title):
        return True
    errors = book.get("errors", "") or ""
    if any(e in errors for e in ["missing_title", "missing_price", "missing_image", "excluded_title"]):
        return True
    return False


def main() -> None:
    config = load_config()
    parsed_file = ROOT / config["feed"]["parsed_file"]
    out_file = ROOT / "output" / "yandex-books-special.csv"
    out_file.parent.mkdir(parents=True, exist_ok=True)

    books = read_csv(parsed_file)

    # Фид «Специальный» Google Рекламы для товарных объявлений.
    # Важное отличие от универсального CSV: картинка называется "Image URL",
    # URL товара — "Final URL", цена передаётся как "199 RUB".
    fieldnames = [
        "ID",
        "Final URL",
        "Image URL",
        "Item title",
        "Item description",
        "Price",
        "Sale price",
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
        if is_excluded(b):
            continue

        offer_id = clean_text(b.get("offer_id", ""))[:100]
        if not offer_id or offer_id in seen_ids:
            continue
        seen_ids.add(offer_id)

        url = clean_text(b.get("url", ""))
        image = clean_text(b.get("image_url", ""))
        title = clean_text(b.get("title", ""))
        description = clean_text(b.get("description", ""))
        price = price_with_currency(b.get("price", ""), "RUB")

        if not url or not image or not is_valid_image(image) or not title or not price:
            continue

        sale_price = ""
        old_price = clean_price(b.get("old_price", ""))
        current_price = clean_price(b.get("price", ""))
        # Если old_price реально выше текущей цены, отдаём старую цену как Price,
        # а текущую как Sale price по логике Google Ads Special feed.
        if old_price and current_price:
            try:
                if float(old_price) > float(current_price):
                    price = price_with_currency(old_price, "RUB")
                    sale_price = price_with_currency(current_price, "RUB")
            except ValueError:
                pass

        internal_currency = clean_text(b.get("internal_currency", ""))
        if not internal_currency:
            internal_currency = "sapphire" if clean_text(b.get("sapphires_price", "")) else "RUB"

        rows.append({
            "ID": offer_id,
            "Final URL": url,
            "Image URL": image,
            "Item title": trim(title, 120),
            "Item description": trim(description, 500),
            "Price": price,
            "Sale price": sale_price,
            "custom_label_0": clean_text(b.get("feed_group", "default")),
            "custom_label_1": internal_currency,
            "custom_label_2": "is_new" if b.get("is_new") == "true" else "",
            "custom_label_3": "is_popular" if b.get("is_popular") == "true" else "",
            "custom_label_4": "is_cheap" if b.get("is_cheap") == "true" else "",
            "custom_score": clean_text(b.get("priority", "50")) or "50",
        })

    with out_file.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated special CSV: {out_file} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
