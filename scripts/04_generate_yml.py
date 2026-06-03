from __future__ import annotations

from datetime import datetime
from xml.sax.saxutils import escape

from common import ROOT, clean_text, load_config, read_csv


def xml(text: str) -> str:
    return escape(clean_text(text), {"'": "&apos;", '"': "&quot;"})


def param(name: str, value: str) -> str:
    if value == "" or value is None:
        return ""
    return f'        <param name="{xml(name)}">{xml(str(value))}</param>\n'


def has_blocking_error(errors: str) -> bool:
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


def main() -> None:
    config = load_config()
    books = read_csv(ROOT / config["feed"]["parsed_file"])
    out = ROOT / config["feed"]["output_file"]
    out.parent.mkdir(parents=True, exist_ok=True)
    shop = config["shop"]
    default_currency = "RUB"

    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append(f'<yml_catalog date="{datetime.now().strftime("%Y-%m-%d %H:%M")}">')
    lines.append("  <shop>")
    lines.append(f"    <name>{xml(shop.get('name', 'RC Books'))}</name>")
    lines.append(f"    <company>{xml(shop.get('company', 'RC Books'))}</company>")
    lines.append(f"    <url>{xml(shop.get('url', 'https://rcbooks.com'))}</url>")
    lines.append("    <currencies>")
    lines.append('      <currency id="RUB" rate="1"/>')
    lines.append("    </currencies>")
    lines.append("    <categories>")
    lines.append('      <category id="1">Книги</category>')
    lines.append("    </categories>")
    lines.append("    <offers>")

    for b in books:
        if has_blocking_error(b.get("errors", "")):
            continue
        offer_id = xml(b.get("offer_id", ""))[:100]
        if not offer_id:
            continue
        available = "true" if b.get("availability", "true") != "false" else "false"
        lines.append(f'      <offer id="{offer_id}" available="{available}">')
        lines.append(f"        <url>{xml(b.get('url', ''))}</url>")
        lines.append(f"        <price>{xml(b.get('price', ''))}</price>")
        if b.get("old_price"):
            lines.append(f"        <oldprice>{xml(b.get('old_price', ''))}</oldprice>")
        lines.append(f"        <currencyId>{default_currency}</currencyId>")
        lines.append("        <categoryId>1</categoryId>")
        lines.append(f"        <picture>{xml(b.get('image_url', ''))}</picture>")
        lines.append(f"        <name>{xml(b.get('title', ''))}</name>")
        if b.get("author"):
            lines.append(f"        <vendor>{xml(b.get('author', ''))}</vendor>")
        lines.append(f"        <description>{xml(b.get('description', ''))}</description>")
        extra = ""
        for key in [
            "internal_currency",
            "sapphires_price",
            "genre",
            "rating",
            "reviews_count",
            "views_count",
            "published_at",
            "is_new",
            "is_popular",
            "is_cheap",
            "feed_group",
            "priority",
        ]:
            extra += param(key, b.get(key, ""))
        if extra:
            lines.append(extra.rstrip("\n"))
        lines.append("      </offer>")

    lines.append("    </offers>")
    lines.append("  </shop>")
    lines.append("</yml_catalog>")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Generated {out}")


if __name__ == "__main__":
    main()
