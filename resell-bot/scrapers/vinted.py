"""
Vinted France scraper — uses Vinted's unofficial catalog API.
No API key required. We just need to maintain a session cookie.
"""

import time
import logging
import requests

logger = logging.getLogger(__name__)

VINTED_BASE = "https://www.vinted.fr"
SEARCH_URL = f"{VINTED_BASE}/api/v2/catalog/items"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Referer": VINTED_BASE,
}


class VintedScraper:
    name = "Vinted"

    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update(HEADERS)
        self._cookie_fetched = False

    def _ensure_cookie(self):
        """Vinted requires a session cookie before using the API."""
        if not self._cookie_fetched:
            try:
                self._session.get(VINTED_BASE, timeout=10)
                self._cookie_fetched = True
            except Exception as e:
                logger.warning(f"[Vinted] Could not fetch session cookie: {e}")

    def search(self, query: str, min_price: float = 0, max_price: float = None) -> list[dict]:
        self._ensure_cookie()

        params = {
            "search_text": query,
            "order": "newest_first",
            "per_page": 96,
            "page": 1,
        }
        if min_price and min_price > 0:
            params["price_from"] = min_price
        if max_price:
            params["price_to"] = max_price

        try:
            resp = self._session.get(SEARCH_URL, params=params, timeout=15)
            if resp.status_code == 401:
                # Cookie expired — refresh and retry once
                self._cookie_fetched = False
                self._ensure_cookie()
                resp = self._session.get(SEARCH_URL, params=params, timeout=15)

            if resp.status_code != 200:
                logger.debug(f"[Vinted] HTTP {resp.status_code} for '{query}'")
                return []

            data = resp.json()
            items = data.get("items", [])

            results = []
            for item in items:
                try:
                    price_str = item.get("price", "0")
                    price = float(str(price_str).replace(",", "."))
                    photo = item.get("photo") or {}
                    results.append({
                        "id": f"vinted_{item['id']}",
                        "title": item.get("title", ""),
                        "price": price,
                        "url": f"{VINTED_BASE}/items/{item['id']}",
                        "platform": "Vinted",
                        "image": photo.get("url", ""),
                        "description": item.get("description", "")[:200],
                    })
                except (KeyError, ValueError, TypeError):
                    continue

            return results

        except requests.RequestException as e:
            logger.warning(f"[Vinted] Request error for '{query}': {e}")
            return []
