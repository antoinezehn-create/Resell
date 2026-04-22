"""
Leboncoin scraper.

Leboncoin uses a React/Next.js frontend. We scrape the search results
page and extract listing data from the embedded __NEXT_DATA__ JSON blob,
which is more stable than parsing HTML directly.
"""

import json
import re
import logging
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://www.leboncoin.fr"
SEARCH_URL = f"{BASE_URL}/recherche"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9",
}


class LeboncoinScraper:
    name = "Leboncoin"

    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update(HEADERS)

    def search(self, query: str, min_price: float = 0, max_price: float = None) -> list[dict]:
        params = {"text": query}
        if max_price:
            params["price"] = f"{int(min_price or 0)}-{int(max_price)}"
        elif min_price and min_price > 0:
            params["price"] = f"{int(min_price)}-max"

        try:
            resp = self._session.get(SEARCH_URL, params=params, timeout=20)
            if resp.status_code != 200:
                logger.debug(f"[Leboncoin] HTTP {resp.status_code} for '{query}'")
                return []

            return self._parse_page(resp.text)

        except requests.RequestException as e:
            logger.warning(f"[Leboncoin] Request error for '{query}': {e}")
            return []

    def _parse_page(self, html: str) -> list[dict]:
        """Extract listings from __NEXT_DATA__ embedded JSON."""
        results = []

        # Try to find the __NEXT_DATA__ script tag
        soup = BeautifulSoup(html, "lxml")
        script = soup.find("script", {"id": "__NEXT_DATA__"})

        if script and script.string:
            try:
                data = json.loads(script.string)
                ads = self._extract_ads_from_next_data(data)
                if ads:
                    return ads
            except (json.JSONDecodeError, KeyError):
                pass

        # Fallback: parse HTML article cards directly
        results = self._parse_html_cards(soup)
        return results

    def _extract_ads_from_next_data(self, data: dict) -> list[dict]:
        """Navigate the Next.js data tree to find ad listings."""
        results = []
        try:
            # The structure varies; try common paths
            props = data.get("props", {})
            page_props = props.get("pageProps", {})

            # Try 'searchData' structure
            search_data = page_props.get("searchData", {})
            ads = search_data.get("ads", [])

            if not ads:
                # Alternative: 'initialData'
                initial = page_props.get("initialData", {})
                ads = initial.get("ads", [])

            for ad in ads:
                try:
                    price_val = None
                    price_info = ad.get("price", [])
                    if isinstance(price_info, list) and price_info:
                        price_val = float(price_info[0])
                    elif isinstance(price_info, (int, float)):
                        price_val = float(price_info)

                    if price_val is None:
                        continue

                    ad_id = str(ad.get("list_id", ad.get("id", "")))
                    title = ad.get("subject", ad.get("title", ""))
                    url = ad.get("url", "")
                    if not url.startswith("http"):
                        url = f"{BASE_URL}{url}"

                    images = ad.get("images", {})
                    image_url = ""
                    if isinstance(images, dict):
                        urls = images.get("urls", [])
                        if urls:
                            image_url = urls[0]

                    results.append({
                        "id": f"lbc_{ad_id}",
                        "title": title,
                        "price": price_val,
                        "url": url,
                        "platform": "Leboncoin",
                        "image": image_url,
                        "description": ad.get("body", "")[:200],
                    })
                except (KeyError, ValueError, TypeError):
                    continue

        except Exception as e:
            logger.debug(f"[Leboncoin] next_data parse error: {e}")

        return results

    def _parse_html_cards(self, soup: BeautifulSoup) -> list[dict]:
        """Fallback HTML card parser."""
        results = []

        # Leboncoin uses data-qa-id="aditem_container" on listing cards
        cards = soup.find_all("li", {"data-qa-id": "aditem_container"})

        if not cards:
            # Try generic article tags
            cards = soup.find_all("article")

        for card in cards:
            try:
                link = card.find("a")
                if not link:
                    continue

                url = link.get("href", "")
                if not url.startswith("http"):
                    url = f"{BASE_URL}{url}"

                # Extract listing ID from URL (format: /ad/..../ID.htm)
                id_match = re.search(r'/(\d+)\.htm', url)
                ad_id = id_match.group(1) if id_match else url

                title_el = card.find(attrs={"data-qa-id": "aditem_title"})
                if not title_el:
                    title_el = card.find(["h2", "h3", "p"])
                title = title_el.get_text(strip=True) if title_el else ""

                price_el = card.find(attrs={"data-qa-id": "aditem_price"})
                if not price_el:
                    price_el = card.find(class_=re.compile(r'price', re.I))
                price_text = price_el.get_text(strip=True) if price_el else ""
                price = _parse_price(price_text)

                if price is None or not title:
                    continue

                results.append({
                    "id": f"lbc_{ad_id}",
                    "title": title,
                    "price": price,
                    "url": url,
                    "platform": "Leboncoin",
                    "image": "",
                    "description": "",
                })
            except Exception:
                continue

        return results


def _parse_price(text: str) -> float | None:
    """Extract a numeric price from a text like '150 €' or '1 500 €'."""
    digits = re.sub(r'[^\d,.]', '', text.replace(" ", "").replace("\xa0", ""))
    digits = digits.replace(",", ".")
    try:
        return float(digits)
    except ValueError:
        return None
