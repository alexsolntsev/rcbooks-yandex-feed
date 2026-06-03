from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from common import (
    Book,
    ROOT,
    clean_text,
    fetch,
    load_config,
    normalize_url,
    parse_price,
    read_csv,
    stable_id_from_url,
    write_csv,
)


def first_value(*values: Any) -> str:
    for value in values:
        text = clean_text(value)
        if text:
            return text
    return ""

def extract_number(value):
    if value is None:
        return ""

    text = str(value)
    match = re.search(r"\d+(?:[.,]\d+)?", text)

    if not match:
        return ""

    return match.group(0).replace(",", ".")

def extract_image_from_value(value) -> str:
    """
    Достаёт URL картинки из разных форматов:
    - обычная строка
    - список картинок
    - JSON-LD объект {"url": "..."} / {"contentUrl": "..."} / {"@id": "..."}

    Важно: в JSON-LD @id иногда указывает не на картинку, а на страницу товара.
    Такие значения отбрасываем, чтобы не получать image_url вида
    https://rcbooks.com/product/{'@id': '...'}.
    """
    if not value:
        return ""

    if isinstance(value, list):
        for item in value:
            result = extract_image_from_value(item)
            if result:
                return result
        return ""

    if isinstance(value, dict):
        for key in ["url", "contentUrl", "thumbnailUrl", "@id"]:
            result = extract_image_from_value(value.get(key))
            if result:
                return result
        return ""

    text = clean_text(str(value))
    if not text or text.startswith("{") or text.startswith("["):
        return ""

    lower = text.lower().split("?")[0]
    looks_like_image = lower.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"))
    if text.startswith(("http://", "https://", "http:/", "https:/")) and not looks_like_image:
        if "/product/" in lower or "/book/" in lower or "/books/" in lower:
            return ""

    return text

def extract_json_ld(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for script in soup.find_all("script", attrs={"type": re.compile("ld\\+json", re.I)}):
        raw = script.string or script.get_text(" ", strip=True)
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            items.extend([x for x in data if isinstance(x, dict)])
        elif isinstance(data, dict):
            if "@graph" in data and isinstance(data["@graph"], list):
                items.extend([x for x in data["@graph"] if isinstance(x, dict)])
            else:
                items.append(data)
    return items


def pick_product_jsonld(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    for item in items:
        typ = item.get("@type") or item.get("type")
        if isinstance(typ, list):
            typ = " ".join(map(str, typ))
        if typ and any(t in str(typ).lower() for t in ["product", "book"]):
            return item
    return items[0] if items else {}


def meta_content(soup: BeautifulSoup, *keys: str) -> str:
    for key in keys:
        tag = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
        if tag and tag.get("content"):
            return clean_text(tag["content"])
    return ""


def selector_text(soup: BeautifulSoup, selectors: List[str]) -> str:
    for selector in selectors:
        if not selector:
            continue

        selector = selector.strip()

        # В config.yml должны быть CSS-селекторы, а не HTML-фрагменты.
        # Например, нельзя: <small style="font-size: 12px;">(45)</small>
        # Нужно: small[style*='font-size: 12px']
        if selector.startswith("<"):
            continue

        try:
            found = soup.select_one(selector)
        except Exception:
            continue

        if not found:
            continue

        if found.name == "meta" and found.get("content"):
            return clean_text(found.get("content"))

        if found.name == "img":
            # На WordPress/ленивой загрузке обложка часто лежит не в src,
            # а в data-src, data-lazy-src, data-original или srcset.
            for attr in ["data-src", "data-lazy-src", "data-original", "src", "srcset"]:
                if found.get(attr):
                    return clean_text(found.get(attr))

        if found.has_attr("content"):
            return clean_text(found["content"])

        return clean_text(found.get_text(" ", strip=True))

    return ""


def clean_image_url(value: Any) -> str:
    """Нормализует URL картинки из meta/img/srcset/JSON-LD."""
    if not value:
        return ""

    value = clean_text(str(value))

    # Если случайно пришёл словарь/список строкой, это не URL картинки.
    if value.startswith("{") or value.startswith("["):
        return ""

    # srcset: берём последний вариант, обычно он самый крупный.
    # Пример: "small.jpg 300w, big.jpg 800w" -> "big.jpg"
    if "," in value and " " in value:
        parts = [part.strip() for part in value.split(",") if part.strip()]
        if parts:
            value = parts[-1].split()[0]
    elif " " in value:
        # srcset без запятых или лишний хвост после URL.
        value = value.split()[0]

    # Чиним частую ошибку JSON-LD/парсинга: https:/site -> https://site
    if value.startswith("https:/") and not value.startswith("https://"):
        value = value.replace("https:/", "https://", 1)
    if value.startswith("http:/") and not value.startswith("http://"):
        value = value.replace("http:/", "http://", 1)

    return value


def normalize_currency_id(value: Any, default: str = "RUB") -> str:
    """Возвращает валидный currencyId для YML.

    Для Яндекс Директа не используем внутренние валюты типа "сапфиры"
    в currencyId: такие товары могут стать невалидными.
    Поэтому currencyId всегда приводим к RUB, если явно не задана валидная валюта.
    """
    text = clean_text(value).upper()
    if not text:
        return default

    mapping = {
        "РУБ": "RUB",
        "РУБ.": "RUB",
        "RUR": "RUB",
        "RUB": "RUB",
        "₽": "RUB",
        "САПФИР": "RUB",
        "САПФИРЫ": "RUB",
        "SAPPHIRE": "RUB",
        "SAPPHIRES": "RUB",
    }
    return mapping.get(text, default)


def selector_text_with_selector(soup: BeautifulSoup, selectors: List[str]) -> tuple[str, str]:
    """Возвращает найденный текст и CSS-селектор, который сработал."""
    for selector in selectors:
        text = selector_text(soup, [selector])
        if text:
            return text, selector
    return "", ""


def detect_internal_currency_from_price(raw_price: str, selector: str) -> str:
    """Определяет внутренний тип цены для доп. параметров фида."""
    text = clean_text(raw_price).lower()
    sel = clean_text(selector).lower()

    if "sapphire" in text or "сапф" in text or "sapphires" in sel:
        return "sapphire"

    if "руб" in text or "₽" in text or "pricev" in sel:
        return "rub"

    return ""


def is_excluded_product_title(title: str, config: Dict[str, Any]) -> bool:
    """Исключает не-книжные товары, например пакеты сапфиров."""
    title = clean_text(title)
    for pattern in config.get("product_exclusions", {}).get("title_regex", []):
        try:
            if re.search(pattern, title, flags=re.IGNORECASE):
                return True
        except re.error:
            continue
    return False

def find_embedded_ids(html: str) -> str:
    patterns = [
        r'"(?:productId|bookId|id)"\s*:\s*"([^"\\]+)"',
        r'"(?:productId|bookId|id)"\s*:\s*(\d+)',
        r"data-(?:product-id|book-id|id)=['\"]([^'\"]+)['\"]",
    ]
    for pat in patterns:
        m = re.search(pat, html, flags=re.I)
        if m:
            return clean_text(m.group(1))
    return ""


def parse_published_at(value: str) -> str:
    if not value:
        return ""
    try:
        return date_parser.parse(value, dayfirst=True).date().isoformat()
    except Exception:
        return ""


def classify(book: Book, config: Dict[str, Any], page_sources: List[str]) -> None:
    cls = config.get("classification", {})
    price = float(book.price) if book.price else 0
    cheap_threshold = float(cls.get("cheap_price_threshold", 150))
    if price and price <= cheap_threshold:
        book.is_cheap = "true"
        book.feed_group = "cheap"

    if book.published_at:
        try:
            dt = date_parser.parse(book.published_at).date()
            age = (datetime.now(timezone.utc).date() - dt).days
            if age <= int(cls.get("new_days", 45)):
                book.is_new = "true"
                book.feed_group = "new"
        except Exception:
            pass
    if any(src in {"new", "novinki", "new_books"} for src in page_sources):
        book.is_new = "true"
        book.feed_group = "new"

    rating = float(book.rating.replace(",", ".")) if book.rating and re.match(r"^\d+([.,]\d+)?$", book.rating) else 0
    reviews = int(re.sub(r"\D", "", book.reviews_count) or 0)
    if rating >= float(cls.get("popular_rating_threshold", 4.5)) and reviews >= int(cls.get("popular_reviews_threshold", 20)):
        book.is_popular = "true"
        if book.feed_group == "default":
            book.feed_group = "popular"
    if any(src in {"popular", "top", "hit"} for src in page_sources):
        book.is_popular = "true"
        if book.feed_group == "default":
            book.feed_group = "popular"


def description_for(book: Book, config: Dict[str, Any]) -> str:
    templates = config.get("description_templates", {})
    if book.is_new == "true":
        return templates.get("new") or templates.get("default", "")
    if book.is_popular == "true":
        return templates.get("popular") or templates.get("default", "")
    if book.is_cheap == "true":
        return templates.get("cheap") or templates.get("default", "")
    return templates.get("default", "")


def parse_book(url: str, source: str, config: Dict[str, Any]) -> Book:
    html = fetch(url, config)
    book = Book(offer_id=stable_id_from_url(url), url=normalize_url(url), currency=normalize_currency_id(config["shop"].get("currency", "RUB")), source=source)
    errors = []
    if not html:
        book.errors = "fetch_failed"
        return book
    soup = BeautifulSoup(html, "html5lib")

    canonical = soup.find("link", rel=lambda x: x and "canonical" in x)
    if canonical and canonical.get("href"):
        book.url = normalize_url(canonical["href"], url)
        book.offer_id = stable_id_from_url(book.url)

    product = pick_product_jsonld(extract_json_ld(soup))
    offers = product.get("offers") if isinstance(product.get("offers"), dict) else {}
    brand = product.get("brand") if isinstance(product.get("brand"), dict) else product.get("brand")
    author = product.get("author") if isinstance(product.get("author"), dict) else product.get("author")
    aggregate = product.get("aggregateRating") if isinstance(product.get("aggregateRating"), dict) else {}

    selectors = config.get("selectors", {})
    embedded_id = find_embedded_ids(html)
    if embedded_id:
        book.offer_id = embedded_id

    title = first_value(
        product.get("name"),
        meta_content(soup, "og:title", "twitter:title"),
        selector_text(soup, selectors.get("title", [])),
        soup.title.string if soup.title else "",
    )
    book.title = title

    if is_excluded_product_title(book.title, config):
        book.errors = "excluded_title_sapphires"
        return book

    book.author = first_value(
        author.get("name") if isinstance(author, dict) else author,
        brand.get("name") if isinstance(brand, dict) else brand,
        selector_text(soup, selectors.get("author", [])),
    )
    # Цена может быть в сапфирах (.sapphires) или рублях (.pricev).
    # В currencyId для Директа всегда отдаём валидную валюту RUB,
    # а внутреннюю валюту сохраняем отдельными param.
    selector_price, price_selector = selector_text_with_selector(soup, selectors.get("price", []))
    raw_price = first_value(offers.get("price"), selector_price)
    book.price = extract_number(parse_price(raw_price))
    book.currency = "RUB"
    book.internal_currency = detect_internal_currency_from_price(raw_price, price_selector)
    if book.internal_currency == "sapphire":
        book.sapphires_price = book.price
    # В JSON-LD поле image может быть строкой, списком или объектом вида
    # {"@id": "..."} / {"url": "..."}. Сначала аккуратно достаём URL,
    # затем fallback на og:image/twitter:image и CSS-селекторы из config.yml.
    raw_image_url = first_value(
        extract_image_from_value(product.get("image")),
        meta_content(soup, "og:image", "twitter:image"),
        selector_text(soup, selectors.get("image_url", [])),
        selector_text(soup, selectors.get("image", [])),
    )
    book.image_url = normalize_url(clean_image_url(raw_image_url), url)
    book.description = first_value(
        product.get("description"),
        meta_content(soup, "description", "og:description"),
        selector_text(soup, selectors.get("description", [])),
    )
    book.rating = first_value(aggregate.get("ratingValue"), selector_text(soup, selectors.get("rating", [])))
    book.reviews_count = extract_number(first_value(aggregate.get("reviewCount"), selector_text(soup, selectors.get("reviews_count", []))))
    book.published_at = parse_published_at(first_value(product.get("datePublished"), product.get("dateCreated")))

    if offers.get("availability"):
        avail = str(offers.get("availability")).lower()
        book.availability = "false" if "outofstock" in avail or "soldout" in avail else "true"

    source_tokens = [source.lower()]
    classify(book, config, source_tokens)
    # Replace content description with ad-safe template by default.
    book.description = description_for(book, config)

    if not book.title:
        errors.append("missing_title")
    if not book.price:
        errors.append("missing_price")
    if not book.image_url:
        errors.append("missing_image")
    if not book.url:
        errors.append("missing_url")
    book.errors = ";".join(errors)
    return book


def main() -> None:
    config = load_config()
    urls_file = ROOT / config["feed"]["urls_file"]
    urls = read_csv(urls_file)
    rows = []
    delay = float(config["crawl"].get("delay_seconds", 0.4))
    for i, row in enumerate(urls, 1):
        book = parse_book(row["url"], row.get("source", "auto"), config)
        rows.append(book.to_dict())
        if i % 25 == 0:
            print(f"Parsed {i}/{len(urls)}")
        time.sleep(delay)
    fieldnames = list(Book(offer_id="", url="").to_dict().keys())
    write_csv(ROOT / config["feed"]["parsed_file"], rows, fieldnames)
    print(f"Parsed {len(rows)} books")


if __name__ == "__main__":
    main()
