"""
PriceCharting.com price fetcher for retro games — web scraper.

Why scraping: The PriceCharting API requires a paid Pro subscription.
We scrape the search results page instead. Results are cached 24h.

PAL games: we append the platform name (e.g. "Super Nintendo") to the
query to prefer European/PAL results where available.
"""

import json
import re
import time
import logging
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from rapidfuzz import fuzz

from utils.matcher import IdentifiedItem

logger = logging.getLogger(__name__)

CACHE_PATH = Path("price_cache_pricecharting.json")
CACHE_TTL = 86400  # 24 hours
FALLBACK_EUR_USD = 0.92

PLATFORM_MAP = {
    "SNES": "Super Nintendo",
    "N64": "Nintendo 64",
    "Game Boy": "Game Boy",
    "Game Boy Color": "Game Boy Color",
    "Game Boy Advance": "Game Boy Advance",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


class PriceChartingPricer:
    def __init__(self, config: dict):
        self._cache: dict = {}
        self._load_cache()
        self._session = requests.Session()
        self._session.headers.update(HEADERS)
        self._eur_rate: float | None = None
        logger.info("[PriceCharting] Using web scraper.")

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
            logger.warning(f"[PriceCharting] Could not save cache: {e}")

    def _fetch_eur_rate(self) -> float:
        """Fetch current USD→EUR rate from a free exchange rate API."""
        try:
            resp = requests.get("https://open.er-api.com/v6/latest/USD", timeout=5)
            if resp.status_code == 200:
                rate = resp.json().get("rates", {}).get("EUR")
                if rate:
                    return float(rate)
        except Exception:
            pass
        return FALLBACK_EUR_USD

    def get_price(self, item: IdentifiedItem) -> tuple[float | None, str]:
        """Return (price_eur, source_description) for a retro game."""
        game_title = item.game_title or item.raw_title
        if not game_title or len(game_title) < 3:
            return None, ""
        return self._lookup_game(game_title, item.platform)

    def _lookup_game(self, title: str, platform: str | None) -> tuple[float | None, str]:
        console = PLATFORM_MAP.get(platform or "", platform or "")
        search_query = f"{title.strip()} {console}".strip() if console else title.strip()

        cache_key = f"pc_{search_query}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached, "PriceCharting (cached)"

        try:
            resp = self._session.get(
                "https://www.pricecharting.com/search-products",
                params={"q": search_query[:80], "type": "videogames"},
                timeout=15,
            )
            if resp.status_code != 200:
                logger.debug(f"[PriceCharting] HTTP {resp.status_code} for '{search_query}'")
                return None, ""

            price_usd, product_name = _parse_search_results(resp.text, title, console)
            if not price_usd:
                return None, ""

            if self._eur_rate is None:
                self._eur_rate = self._fetch_eur_rate()
            price_eur = round(price_usd * self._eur_rate, 2)
            self._set_cached(cache_key, price_eur)
            return price_eur, f"PriceCharting ({product_name})"

        except Exception as e:
            logger.warning(f"[PriceCharting] Error for '{title}': {e}")
            return None, ""

    def _get_cached(self, key: str) -> float | None:
        entry = self._cache.get(key)
        if entry and time.time() - entry["ts"] < CACHE_TTL:
            return entry["price"]
        return None

    def _set_cached(self, key: str, price: float):
        self._cache[key] = {"price": price, "ts": time.time()}
        self._save_cache()


def _parse_search_results(html: str, title: str, console: str) -> tuple[float | None, str]:
    """
    Extract the best-matching game price from the PriceCharting search results page.
    Returns (price_usd_float, product_name_str).
    """
    soup = BeautifulSoup(html, "lxml")
    title_lower = title.lower()
    console_lower = console.lower() if console else ""

    best_score = 0
    best_price = None
    best_name = ""

    # Each search result row is a <tr> in table#games_table
    table = soup.find("table", {"id": "games_table"})
    if not table:
        # Redirect to product page directly (single result)
        return _parse_product_page(soup)

    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue

        product_name = cells[0].get_text(strip=True)
        console_cell = cells[1].get_text(strip=True) if len(cells) > 1 else ""

        # Score by name similarity + platform match
        name_score = fuzz.token_set_ratio(title_lower, product_name.lower())
        platform_bonus = 15 if console_lower and console_lower in console_cell.lower() else 0
        score = name_score + platform_bonus

        if score > best_score and score >= 55:
            # Column order: 0=name, 1=console, 2=loose, 3=CIB, 4=new
            price = None
            if len(cells) > 3:
                price = _parse_usd_cell(cells[3])  # CIB preferred
            if not price and len(cells) > 2:
                price = _parse_usd_cell(cells[2])  # loose fallback
            if price and 0 < price < 5000:
                best_score = score
                best_price = price
                best_name = product_name

    return best_price, best_name


def _parse_product_page(soup: BeautifulSoup) -> tuple[float | None, str]:
    """Parse a direct product page when the search redirected to it."""
    title_el = soup.find("h1", {"id": "product_name"})
    product_name = title_el.get_text(strip=True) if title_el else ""

    # PriceCharting product pages use these specific element IDs for prices
    for price_id in ("complete_price", "used_price", "new_price"):
        el = soup.find(id=price_id)
        if el:
            price = _parse_usd_text(el.get_text(strip=True))
            if price and 0 < price < 5000:
                return price, product_name

    return None, product_name


def _parse_usd_cell(cell) -> float | None:
    return _parse_usd_text(cell.get_text(strip=True))


def _parse_usd_text(text: str) -> float | None:
    """Extract a USD price like '$12.34' or '12.34' from a string."""
    match = re.search(r'\$?\s*([\d,]+\.?\d*)', text.replace(",", ""))
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    return None
