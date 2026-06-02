from __future__ import annotations

import csv
import hashlib
import html
import json
import re
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urljoin, urlparse, urlunparse

import requests
import yaml
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

ROOT = Path(__file__).resolve().parents[1]


def load_config() -> Dict[str, Any]:
    with open(ROOT / "input" / "config.yml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: Optional[List[str]] = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        keys = set()
        for row in rows:
            keys.update(row.keys())
        fieldnames = sorted(keys)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def normalize_url(url: str, base: Optional[str] = None) -> str:
    if not url:
        return ""
    if base:
        url = urljoin(base, url)
    parsed = urlparse(url.strip())
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc.lower()
    path = re.sub(r"/{2,}", "/", parsed.path)
    # Strip trailing slash except root.
    if len(path) > 1:
        path = path.rstrip("/")
    return urlunparse((scheme, netloc, path, "", "", ""))


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    value = html.unescape(str(value))
    value = re.sub(r"\s+", " ", value).strip()
    return value


def parse_price(value: Any) -> str:
    text = clean_text(value).replace("\xa0", " ")
    # Keep first decimal-looking number.
    match = re.search(r"\d+(?:[\s.,]\d{3})*(?:[.,]\d{1,2})?|\d+", text)
    if not match:
        return ""
    number = match.group(0).replace(" ", "").replace(",", ".")
    try:
        val = float(number)
        if val.is_integer():
            return str(int(val))
        return f"{val:.2f}"
    except ValueError:
        return ""


def stable_id_from_url(url: str) -> str:
    parsed = urlparse(normalize_url(url))
    slug = parsed.path.strip("/").split("/")[-1]
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", slug)[:70]
    if not slug:
        slug = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    return f"book_{slug}"


def boolish(value: Any) -> Optional[bool]:
    if value is None or value == "":
        return None
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "да", "истина"}:
        return True
    if text in {"0", "false", "no", "n", "нет", "ложь"}:
        return False
    return None


def fetch(url: str, config: Dict[str, Any]) -> Optional[str]:
    headers = {"User-Agent": config["crawl"].get("user_agent", "Mozilla/5.0")}
    try:
        resp = requests.get(url, headers=headers, timeout=config["crawl"].get("timeout_seconds", 20))
        if resp.status_code >= 400:
            return None
        resp.encoding = resp.apparent_encoding or "utf-8"
        return resp.text
    except requests.RequestException:
        return None


def is_book_url(url: str, config: Dict[str, Any]) -> bool:
    norm = normalize_url(url)
    path = urlparse(norm).path
    for bad in config["crawl"].get("exclude_url_patterns", []):
        if bad in path:
            return False
    patterns = config["crawl"].get("book_url_patterns", [])
    return any(pat in path for pat in patterns)


@dataclass
class Book:
    offer_id: str
    url: str
    title: str = ""
    author: str = ""
    price: str = ""
    old_price: str = ""
    currency: str = "RUB"
    image_url: str = ""
    category: str = "Книги"
    category_id: str = "1"
    description: str = ""
    genre: str = ""
    rating: str = ""
    reviews_count: str = ""
    views_count: str = ""
    published_at: str = ""
    availability: str = "true"
    is_new: str = "false"
    is_popular: str = "false"
    is_cheap: str = "false"
    feed_group: str = "default"
    priority: str = "50"
    source: str = ""
    errors: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
