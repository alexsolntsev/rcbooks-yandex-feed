from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List
from xml.sax.saxutils import escape

from common import ROOT, clean_text, load_config, read_csv


BAD_TITLE_RE = re.compile(
    r"^\s*\d+\s+(?:сапфир(?:ов|а|ы)?|sapphire(?:s)?)\s*[-–—]\s*RC Books\s*$",
    re.IGNORECASE,
)


def xml(text: Any) -> str:
    return escape(clean_text(text), {"'": "&apos;", '"': "&quot;"})


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


def normalize_price(value: str) -> str:
    value = clean_text(value).replace(",", ".")
    if not value:
        return ""
    try:
        number = float(value)
        return f"{number:.2f} RUB"
    except ValueError:
        match = re.search(r"\d+(?:\.\d+)?", value)
        if not match:
            return ""
        number = float(match.group(0))
        return f"{number:.2f} RUB"


def blocking_error(errors: str) -> bool:
    if not errors:
        return False
    blocking = {
        "missing_title",
        "missing_price",
        "missing_image",
        "missing_url",
        "excluded_title_sapphires",
        "fetch_failed",
    }
    return any(e in blocking for e in errors.split(";"))


def tag(name: str, value: str) -> str:
    if not value:
        return ""
    return f"      <g:{name}>{xml(value)}</g:{name}>\n"


def main() -> None:
    config = load_config()
    books = read_csv(ROOT / config["feed"]["parsed_file"])
    output_file = ROOT / config["feed"].get("google_output_file", "output/yandex-books-google.xml")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    shop = config.get("shop", {})
    shop_name = shop.get("name", "RC Books")
    shop_url = shop.get("url", "https://rcbooks.com")

    lines: List[str] = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append('<rss version="2.0" xmlns:g="http://base.google.com/ns/1.0">')
    lines.append('  <channel>')
    lines.append(f"    <title>{xml(shop_name)}</title>")
    lines.append(f"    <link>{xml(shop_url)}</link>")
    lines.append("    <description>RC Books product feed</description>")
    lines.append(f"    <lastBuildDate>{datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')}</lastBuildDate>")

    seen_ids = set()
    count = 0
    for b in books:
        if blocking_error(b.get("errors", "")):
            continue
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
        if not url or not image or not is_valid_image_url(image) or not price:
            continue

        availability = "in_stock" if b.get("availability", "true") != "false" else "out_of_stock"
        description = short_text(b.get("description", ""), 500) or short_text(title, 500)
        product_type = clean_text(b.get("genre", "")) or "Книги"
        brand = clean_text(b.get("author", "")) or "RC Books"

        lines.append("    <item>")
        lines.append(tag("id", offer_id).rstrip())
        lines.append(tag("title", short_text(title, 150)).rstrip())
        lines.append(tag("description", description).rstrip())
        lines.append(tag("link", url).rstrip())
        lines.append(tag("image_link", image).rstrip())
        lines.append(tag("price", price).rstrip())
        old_price = normalize_price(b.get("old_price", ""))
        if old_price and old_price != price:
            lines.append(tag("sale_price", price).rstrip())
        lines.append(tag("availability", availability).rstrip())
        lines.append(tag("condition", "new").rstrip())
        lines.append(tag("product_type", product_type).rstrip())
        lines.append(tag("brand", brand).rstrip())
        # custom labels for EPK filters
        if b.get("feed_group"):
            lines.append(tag("custom_label_0", b.get("feed_group", "")).rstrip())
        if b.get("internal_currency"):
            lines.append(tag("custom_label_1", b.get("internal_currency", "")).rstrip())
        if b.get("is_new"):
            lines.append(tag("custom_label_2", "is_new" if b.get("is_new") == "true" else "not_new").rstrip())
        if b.get("is_popular"):
            lines.append(tag("custom_label_3", "is_popular" if b.get("is_popular") == "true" else "not_popular").rstrip())
        if b.get("is_cheap"):
            lines.append(tag("custom_label_4", "is_cheap" if b.get("is_cheap") == "true" else "not_cheap").rstrip())
        if b.get("priority"):
            lines.append(tag("custom_score", b.get("priority", "")).rstrip())
        lines.append("    </item>")
        count += 1

    lines.append("  </channel>")
    lines.append("</rss>")
    output_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Generated {output_file} with {count} items")


if __name__ == "__main__":
    main()
