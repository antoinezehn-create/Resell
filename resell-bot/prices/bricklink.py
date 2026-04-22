"""
BrickLink / Brick Economy price fetcher — scrapes brick-economy.com.

Why scraping: BrickLink's OAuth API requires a seller account with buyer
feedback. We use brick-economy.com as the primary source (friendlier to
scrape) and fall back to bricklink.com catalog pages.

Cache: 24h TTL to avoid hammering the site.
"""

import json
import re
import time
import logging
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from utils.matcher import IdentifiedItem

logger = logging.getLogger(__name__)

CACHE_PATH = Path("price_cache_bricklink.json")
CACHE_TTL = 86400  # 24 hours

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


class BrickLinkPricer:
    def __init__(self, config: dict):
        self._cache: dict = {}
        self._load_cache()
        self._session = requests.Session()
        self._session.headers.update(HEADERS)
        logger.info("[BrickLink] Using web scraper (brick-economy.com).")

    def _load_cache(self):
        if CACHE_PATH.exists():
            try:
                with open(CACHE_PATH, "r") as f:
                    self._cache = json.load(f)
            except Exception:
                self._cache = {}

    def _save_cache(self):
        try:
            with open(CACHE_PATH, "w") as f:
                json.dump(self._cache, f)
        except OSError as e:
            logger.warning(f"[BrickLink] Could not save cache: {e}")

    def get_price(self, item: IdentifiedItem) -> tuple[float | None, str]:
        """Return (avg_used_price_eur, source_description) for a Lego set."""
        if item.set_number:
            return self._get_by_set_number(item.set_number)
        return None, ""

    def _get_by_set_number(self, set_number: str) -> tuple[float | None, str]:
        cache_key = f"set_{set_number}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached, "Brick Economy (cached)"

        # Try brick-economy.com first
        price = self._scrape_brick_economy(set_number)
        if price:
            self._set_cached(cache_key, price)
            return price, f"Brick Economy avg used (#{set_number})"

        # Fallback: bricklink.com catalog page
        price = self._scrape_bricklink(set_number)
        if price:
            self._set_cached(cache_key, price)
            return price, f"BrickLink avg sold (#{set_number})"

        return None, ""

    def _scrape_brick_economy(self, set_number: str) -> float | None:
        """Scrape the average used price from brick-economy.com."""
        url = f"https://www.brick-economy.com/set/{set_number}"
        try:
            resp = self._session.get(url, timeout=15)
            if resp.status_code != 200:
                logger.debug(f"[BrickEconomy] HTTP {resp.status_code} for set {set_number}")
                return None

            soup = BeautifulSoup(resp.text, "lxml")
            text = soup.get_text(" ", strip=True)

            # Look for EUR price near "used" keyword
            return _extract_eur_price_near_keyword(text, ["used", "occasion"])

        except Exception as e:
            logger.debug(f"[BrickEconomy] Error for set {set_number}: {e}")
        return None

    def _scrape_bricklink(self, set_number: str) -> float | None:
        """Scrape average 6-month sold price from bricklink.com catalog page."""
        url = f"https://www.bricklink.com/v2/catalog/catalogitem.page?S={set_number}-1"
        try:
            resp = self._session.get(url, timeout=15)
            if resp.status_code != 200:
                return None

            soup = BeautifulSoup(resp.text, "lxml")
            text = soup.get_text(" ", strip=True)

            # BrickLink shows "Avg Price: US $XX.XX" in the price guide section
            price_usd = _extract_usd_price(text)
            if price_usd:
                # Convert USD to EUR at a fixed rate
                return round(price_usd * 0.92, 2)

        except Exception as e:
            logger.debug(f"[BrickLink] Scrape error for set {set_number}: {e}")
        return None

    def _get_cached(self, key: str) -> float | None:
        entry = self._cache.get(key)
        if entry and time.time() - entry["ts"] < CACHE_TTL:
            return entry["price"]
        return None

    def _set_cached(self, key: str, price: float):
        self._cache[key] = {"price": price, "ts": time.time()}
        self._save_cache()


def _extract_eur_price_near_keyword(text: str, keywords: list[str]) -> float | None:
    """Find a EUR price that appears within 100 chars of any of the given keywords."""
    text_lower = text.lower()
    for kw in keywords:
        idx = text_lower.find(kw)
        if idx == -1:
            continue
        window = text[max(0, idx - 50): idx + 150]
        match = re.search(r'€\s*([\d\s]+[,.]?\d+)', window)
        if match:
            price = _parse_float(match.group(1))
            if price and 0 < price < 2000:
                return price
    return None


def _extract_usd_price(text: str) -> float | None:
    """Find a USD price like 'US $45.00' or '$45.00' in text."""
    match = re.search(r'\$\s*([\d,]+\.?\d*)', text)
    if match:
        return _parse_float(match.group(1))
    return None


def _parse_float(s: str) -> float | None:
    """Parse a price string like '1 234,56' or '45.00' to float."""
    cleaned = re.sub(r'[^\d,.]', '', s.strip())
    # Handle European format: 1.234,56
    if ',' in cleaned and '.' in cleaned:
        if cleaned.index(',') > cleaned.index('.'):
            cleaned = cleaned.replace('.', '').replace(',', '.')
        else:
            cleaned = cleaned.replace(',', '')
    elif ',' in cleaned:
        cleaned = cleaned.replace(',', '.')
    try:
        return float(cleaned)
    except ValueError:
        return None
