from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Set
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from common import ROOT, fetch, is_book_url, load_config, normalize_url, read_csv, write_csv


def parse_sitemap(xml_text: str) -> List[str]:
    urls: List[str] = []
    try:
        root = ET.fromstring(xml_text)
        for loc in root.iter():
            if loc.tag.endswith("loc") and loc.text:
                urls.append(loc.text.strip())
    except ET.ParseError:
        urls += re.findall(r"<loc>(.*?)</loc>", xml_text, flags=re.I | re.S)
    return urls


def collect_from_sitemap(url: str, config: Dict) -> Set[str]:
    found: Set[str] = set()
    seen_sitemaps: Set[str] = set()
    queue = [normalize_url(url)]
    while queue:
        current = queue.pop(0)
        if current in seen_sitemaps:
            continue
        seen_sitemaps.add(current)
        xml = fetch(current, config)
        if not xml:
            continue
        for loc in parse_sitemap(xml):
            loc = normalize_url(loc)
            if loc.endswith(".xml") or "sitemap" in urlparse(loc).path:
                queue.append(loc)
            elif is_book_url(loc, config):
                found.add(loc)
    return found


def collect_from_catalog(start_url: str, config: Dict) -> Set[str]:
    found: Set[str] = set()
    visited: Set[str] = set()
    queue = [normalize_url(start_url)]
    domain = urlparse(start_url).netloc
    max_pages = int(config["crawl"].get("max_pages_per_catalog", 300))
    delay = float(config["crawl"].get("delay_seconds", 0.4))

    while queue and len(visited) < max_pages:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)
        html = fetch(current, config)
        if not html:
            continue
        soup = BeautifulSoup(html, "html5lib")
        for a in soup.find_all("a", href=True):
            href = normalize_url(a["href"], current)
            if not href or urlparse(href).netloc != domain:
                continue
            if is_book_url(href, config):
                found.add(href)
            # Follow likely catalog/pagination pages, not all pages.
            path = urlparse(href).path
            if any(token in path for token in ["catalog", "books", "genre", "popular", "new"]):
                if href not in visited and href not in queue:
                    queue.append(href)
        time.sleep(delay)
    return found


def main() -> None:
    config = load_config()
    seeds = read_csv(ROOT / "input" / "seed_urls.csv")
    all_urls: Set[str] = set()
    rows = []

    for seed in seeds:
        seed_type = (seed.get("type") or "").strip().lower()
        url = normalize_url(seed.get("url") or "")
        if not url:
            continue
        if seed_type == "sitemap" or url.endswith(".xml"):
            urls = collect_from_sitemap(url, config)
        else:
            urls = collect_from_catalog(url, config)
        for u in urls:
            all_urls.add(u)
            rows.append({"url": u, "source": seed_type or "catalog", "status": "active"})

    rows = [{"url": u, "source": "auto", "status": "active"} for u in sorted(all_urls)]
    write_csv(ROOT / config["feed"]["urls_file"], rows, ["url", "source", "status"])
    print(f"Collected {len(rows)} unique book URLs")


if __name__ == "__main__":
    main()
