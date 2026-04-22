"""
Catawiki scraper — uses their public buyer API to get open auction lots.
Results include current bid price (not final price), so we compare
against a conservative estimate (current bid as the "listing price").
"""

import logging
import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://www.catawiki.com"
API_URL = f"{BASE_URL}/buyer/api/v1/lots"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Referer": BASE_URL,
}


class CatawiKiScraper:
    name = "Catawiki"

    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update(HEADERS)

    def search(self, query: str, min_price: float = 0, max_price: float = None) -> list[dict]:
        params = {
            "q": query,
            "per_page": 50,
            "status": "open",          # Only open (not ended) auctions
            "locale": "fr",
        }
        if min_price and min_price > 0:
            params["reserve_price_from"] = int(min_price)

        try:
            resp = self._session.get(API_URL, params=params, timeout=15)

            if resp.status_code == 404:
                # Some queries return 404 when no results
                return []

            if resp.status_code != 200:
                logger.debug(f"[Catawiki] HTTP {resp.status_code} for '{query}'")
                return []

            data = resp.json()
            lots = data if isinstance(data, list) else data.get("lots", data.get("data", []))

            results = []
            for lot in lots:
                try:
                    lot_id = str(lot.get("id", ""))
                    title = lot.get("title", lot.get("name", ""))

                    # Use reserve price (minimum bid), or current bid if available
                    price = None
                    reserve = lot.get("reserve_price")
                    current_bid = lot.get("current_price", lot.get("current_bid"))

                    if current_bid:
                        price = float(current_bid)
                    elif reserve:
                        price = float(reserve)

                    if price is None or not title:
                        continue

                    url = lot.get("url", f"{BASE_URL}/en/l/{lot_id}")
                    if not url.startswith("http"):
                        url = f"{BASE_URL}{url}"

                    image = ""
                    images = lot.get("images", [])
                    if images and isinstance(images, list):
                        image = images[0].get("url", "") if isinstance(images[0], dict) else ""

                    results.append({
                        "id": f"catawiki_{lot_id}",
                        "title": title,
                        "price": price,
                        "url": url,
                        "platform": "Catawiki",
                        "image": image,
                        "description": lot.get("description", "")[:200],
                    })
                except (KeyError, ValueError, TypeError):
                    continue

            return results

        except requests.RequestException as e:
            logger.warning(f"[Catawiki] Request error for '{query}': {e}")
            return []
