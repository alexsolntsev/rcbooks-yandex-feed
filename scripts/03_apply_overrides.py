from __future__ import annotations

from typing import Dict, List

from common import ROOT, boolish, clean_text, load_config, read_csv, write_csv

FIELDS = [
    "offer_id", "title", "author", "price", "currency", "image_url", "is_new", "is_popular", "is_cheap",
    "description", "priority"
]

OVERRIDE_MAP = {
    "force_offer_id": "offer_id",
    "force_title": "title",
    "force_author": "author",
    "force_price": "price",
    "force_currency": "currency",
    "force_internal_currency": "internal_currency",
    "force_sapphires_price": "sapphires_price",
    "force_image_url": "image_url",
    "force_is_new": "is_new",
    "force_is_popular": "is_popular",
    "force_is_cheap": "is_cheap",
    "custom_description": "description",
    "priority": "priority",
}


def main() -> None:
    config = load_config()
    books = read_csv(ROOT / config["feed"]["parsed_file"])
    overrides = read_csv(ROOT / "input" / "overrides.csv")
    by_url: Dict[str, Dict[str, str]] = {row.get("url", "").strip(): row for row in overrides if row.get("url")}

    final: List[Dict[str, str]] = []
    for book in books:
        ov = by_url.get(book.get("url", "")) or {}
        exclude = boolish(ov.get("exclude"))
        if exclude is True:
            continue
        for src, dst in OVERRIDE_MAP.items():
            val = clean_text(ov.get(src, ""))
            if val:
                if dst.startswith("is_"):
                    parsed = boolish(val)
                    if parsed is not None:
                        book[dst] = "true" if parsed else "false"
                else:
                    book[dst] = val
        # currencyId в YML должен оставаться валидной валютой для Яндекса.
        # Если вручную указали сапфиры, сохраняем это как internal_currency,
        # но currencyId всё равно ставим RUB.
        if clean_text(book.get("currency", "")).lower() in {"сапфиры", "сапфир", "sapphire", "sapphires"}:
            book["internal_currency"] = "sapphire"
            book["sapphires_price"] = book.get("sapphires_price") or book.get("price", "")
            book["currency"] = "RUB"
        elif not book.get("currency"):
            book["currency"] = "RUB"

        # Update feed_group after forced labels.
        if book.get("is_new") == "true":
            book["feed_group"] = "new"
        elif book.get("is_popular") == "true":
            book["feed_group"] = "popular"
        elif book.get("is_cheap") == "true":
            book["feed_group"] = "cheap"
        final.append(book)

    write_csv(ROOT / config["feed"]["parsed_file"], final, list(books[0].keys()) if books else None)
    print(f"Applied overrides. Final rows: {len(final)}")


if __name__ == "__main__":
    main()
