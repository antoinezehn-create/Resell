"""
Cardmarket price fetcher — uses the official Cardmarket API (MKM API v2.0).
Returns the trend price for a Pokemon card.

Auth: OAuth 1.0a with 4 credentials.
Get credentials at: https://api.cardmarket.com/ws/documentation/API_2.0:Auth

Free tier allows 100 requests/day — enough for our use case with caching.
Price cache: 24h TTL to stay within quota.
"""

import json
import time
import logging
import os
import re
from pathlib import Path

import requests
from requests_oauthlib import OAuth1
from bs4 import BeautifulSoup

from utils.matcher import IdentifiedItem

logger = logging.getLogger(__name__)

CARDMARKET_API = "https://api.cardmarket.com/ws/v2.0/output.json"
CACHE_PATH = Path("price_cache_cardmarket.json")
CACHE_TTL = 86400  # 24 hours

# Cardmarket game ID for Pokemon TCG
POKEMON_GAME_ID = 1


class CardmarketPricer:
    def __init__(self, config: dict):
        app_token = os.environ.get("CARDMARKET_APP_TOKEN") or config.get("app_token", "")
        app_secret = os.environ.get("CARDMARKET_APP_SECRET") or config.get("app_secret", "")
        access_token = os.environ.get("CARDMARKET_ACCESS_TOKEN") or config.get("access_token", "")
        access_secret = os.environ.get("CARDMARKET_ACCESS_SECRET") or config.get("access_token_secret", "")

        self._auth = OAuth1(app_token, app_secret, access_token, access_secret)
        self._cache: dict = {}
        self._load_cache()
        self._enabled = bool(app_token and app_secret and access_token and access_secret)

        if not self._enabled:
            logger.warning("[Cardmarket] No API credentials — using web scraper fallback.")
        self._scrape_session = requests.Session()
        self._scrape_session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9",
        })

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
            logger.warning(f"[Cardmarket] Could not save cache: {e}")

    def get_price(self, item: IdentifiedItem) -> tuple[float | None, str]:
        """
        Return (trend_price_eur, source_description) for a Pokemon item.
        Uses OAuth API when keys are available; falls back to web scraping.
        """
        search_term = item.card_name or item.raw_title
        if not search_term or len(search_term) < 3:
            return None, ""

        search_term = _clean_card_name(search_term)

        if self._enabled:
            return self._search_product(search_term, item.card_set)
        else:
            return self._scrape_fallback(search_term)

    def _search_product(self, name: str, card_set: str | None) -> tuple[float | None, str]:
        cache_key = f"cm_{name[:40]}_{card_set or ''}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached, "Cardmarket trend (cached)"

        try:
            resp = requests.get(
                f"{CARDMARKET_API}/products/find",
                params={
                    "search": name[:60],
                    "exact": "false",
                    "idGame": POKEMON_GAME_ID,
                    "idLanguage": 2,  # French preferred, falls back to English
                },
                auth=self._auth,
                timeout=10,
            )

            if resp.status_code == 204:
                # No results
                return None, ""

            if resp.status_code != 200:
                logger.debug(f"[Cardmarket] HTTP {resp.status_code} for '{name}'")
                return None, ""

            data = resp.json()
            products = data.get("product", [])
            if not products:
                return None, ""

            # Score products: prefer matches in the right set
            best = _pick_best_product(products, name, card_set)
            if not best:
                return None, ""

            price_info = best.get("priceGuide", {})
            # Prefer TREND price; fall back to AVG, then SELL
            price = price_info.get("TREND") or price_info.get("AVG") or price_info.get("SELL")

            if price is None:
                return None, ""

            price = float(price)
            self._set_cached(cache_key, price)
            product_name = best.get("enName") or best.get("locName") or name
            return price, f"Cardmarket trend ({product_name})"

        except Exception as e:
            logger.warning(f"[Cardmarket] Error for '{name}': {e}")
            return None, ""

    def _scrape_fallback(self, name: str) -> tuple[float | None, str]:
        """Scrape Cardmarket search page for the trend price when API keys are missing."""
        cache_key = f"cm_scrape_{name[:40]}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached, "Cardmarket trend scrape (cached)"

        url = "https://www.cardmarket.com/en/Pokemon/Products/Search"
        try:
            resp = self._scrape_session.get(
                url,
                params={"searchString": name[:60]},
                timeout=15,
            )
            if resp.status_code != 200:
                logger.debug(f"[Cardmarket] Scrape HTTP {resp.status_code} for '{name}'")
                return None, ""

            soup = BeautifulSoup(resp.text, "lxml")
            price = _extract_trend_price_from_search(soup)
            if price is None:
                return None, ""

            self._set_cached(cache_key, price)
            return price, f"Cardmarket trend scrape ({name})"

        except Exception as e:
            logger.warning(f"[Cardmarket] Scrape error for '{name}': {e}")
            return None, ""

    def _get_cached(self, key: str) -> float | None:
        entry = self._cache.get(key)
        if entry and time.time() - entry["ts"] < CACHE_TTL:
            return entry["price"]
        return None

    def _set_cached(self, key: str, price: float):
        self._cache[key] = {"price": price, "ts": time.time()}
        self._save_cache()


def _clean_card_name(name: str) -> str:
    """Remove noise to get a clean card/product name for searching."""
    # Remove common French noise
    noise = re.compile(
        r'\b(carte|cartes|pokemon|pokémon|collection|lot|rare|holo|'
        r'occasion|neuf|psa|bgs|cgc|grade|graded|lot\s+de|'
        r'vendu|offre|urgente?)\b',
        re.IGNORECASE
    )
    clean = noise.sub("", name)
    clean = re.sub(r'\s+', ' ', clean).strip(" -,")
    return clean[:60]


def _pick_best_product(products: list, query: str, card_set: str | None) -> dict | None:
    """Score products by relevance and return the best match."""
    if not products:
        return None

    query_lower = query.lower()
    set_lower = (card_set or "").lower()

    scored = []
    for p in products:
        score = 0
        name = (p.get("enName") or p.get("locName") or "").lower()

        # Name match
        if query_lower in name or name in query_lower:
            score += 10
        # Set match
        if set_lower and set_lower in str(p).lower():
            score += 5
        # Has price info
        if p.get("priceGuide"):
            score += 3

        scored.append((score, p))

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1] if scored else products[0]


def _extract_trend_price_from_search(soup: BeautifulSoup) -> float | None:
    """Extract the trend price from the first Cardmarket search result."""
    # Look for prices in the search results — Cardmarket uses various price elements
    for el in soup.find_all(["span", "div"], class_=re.compile(r'price', re.I)):
        text = el.get_text(strip=True)
        # Match "45,99 €" or "45.99 €"
        match = re.search(r'([\d]+[,.][\d]{2})\s*€', text)
        if match:
            try:
                val = float(match.group(1).replace(',', '.'))
                if 0 < val < 10000:
                    return val
            except ValueError:
                continue
    return None
