# Resell Bot Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace broken/paid API pricers with working web scrapers, fix a Leboncoin bug, align secret names across the project, and add the Telegram chat ID helper script.

**Architecture:** Each price module becomes self-contained — it tries scraping the primary source, falls back to an alternative, and caches results 24h in a local JSON file. No new dependencies are needed (beautifulsoup4 + lxml + requests are already in requirements.txt).

**Tech Stack:** Python 3.11, requests, BeautifulSoup4, lxml, rapidfuzz (already installed)

---

## File Map

| File | Action | Why |
|------|--------|-----|
| `prices/bricklink.py` | **Rewrite** | OAuth API requires seller account with buyer feedback — scrape instead |
| `prices/pricecharting.py` | **Rewrite** | Official API is paid — scrape instead |
| `prices/cardmarket.py` | **Modify** | Add scraper fallback when OAuth keys are missing |
| `scrapers/leboncoin.py` | **Fix line 43** | min_price is overwritten to 0 when max_price is also passed |
| `main.py` | **Fix line 157** | Reads `TELEGRAM_TOKEN`; rename to `TELEGRAM_BOT_TOKEN` to match secret name |
| `.github/workflows/bot.yml` | **Fix** | Rename `TELEGRAM_TOKEN` → `TELEGRAM_BOT_TOKEN`, remove unused BrickLink/PriceCharting secrets |
| `get_chat_id.py` | **Create** | Helper script for user to discover their Telegram Chat ID |

---

### Task 1: Rewrite `prices/bricklink.py` — scrape Brick Economy

**Files:**
- Modify: `prices/bricklink.py`

The BrickLink OAuth API requires the account to have at least 1 buyer feedback, which the user doesn't have. We scrape `https://www.brick-economy.com/set/{set_number}` instead — it's more scraper-friendly and shows the average used price.

- [ ] **Step 1: Replace the entire file with the scraper implementation**

```python
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
        with open(CACHE_PATH, "w") as f:
            json.dump(self._cache, f)

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

            # brick-economy shows prices in a table; look for "Used" avg price
            # The page has sections like "Current used prices" with avg values
            text = soup.get_text(" ", strip=True)

            # Pattern: look for EUR price near "used" keyword
            # e.g. "Average used price: €45.00" or similar
            price = _extract_eur_price_near_keyword(text, ["used", "occasion"])
            if price:
                return price

            # Fallback: grab first EUR price on the page
            match = re.search(r'€\s*([\d\s]+[,.]?\d*)', text)
            if match:
                return _parse_float(match.group(1))

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
        # Search for €XX or XX€ within a window around the keyword
        window = text[max(0, idx - 50): idx + 150]
        match = re.search(r'€\s*([\d\s]+[,.]?\d+)', window)
        if match:
            price = _parse_float(match.group(1))
            if price and price > 0:
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
```

- [ ] **Step 2: Verify the file saved correctly**

```bash
python -c "from prices.bricklink import BrickLinkPricer; p = BrickLinkPricer({}); print('OK')"
```

Expected: `[BrickLink] Using web scraper (brick-economy.com).` then `OK`

---

### Task 2: Rewrite `prices/pricecharting.py` — scrape the website

**Files:**
- Modify: `prices/pricecharting.py`

The PriceCharting Pro API is paid. We scrape `https://www.pricecharting.com/search-products?q={query}&type=videogames` and extract the first matching result's loose/CIB price from the HTML table. The existing fuzzy-matching logic (`_find_best_match`) is good and we keep it — we just replace the HTTP call.

- [ ] **Step 1: Replace the entire file with the scraper implementation**

```python
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
        self._eur_rate = self._fetch_eur_rate()
        logger.info("[PriceCharting] Using web scraper.")

    def _load_cache(self):
        if CACHE_PATH.exists():
            try:
                with open(CACHE_PATH, "r") as f:
                    self._cache = json.load(f)
            except Exception:
                self._cache = {}

    def _save_cache(self):
        with open(CACHE_PATH, "w") as f:
            json.dump(self._cache, f)

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

        cache_key = f"pc_{search_query[:50]}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached, "PriceCharting (cached)"

        url = "https://www.pricecharting.com/search-products"
        try:
            resp = self._session.get(
                url,
                params={"q": search_query[:80], "type": "videogames"},
                timeout=15,
            )
            if resp.status_code != 200:
                logger.debug(f"[PriceCharting] HTTP {resp.status_code} for '{search_query}'")
                return None, ""

            price_usd, product_name = _parse_search_results(resp.text, title, console)
            if not price_usd:
                return None, ""

            price_eur = round(price_usd * self._eur_rate, 2)
            self._set_cached(cache_key, price_eur)
            return price_eur, f"PriceCharting CIB ({product_name})"

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
    from rapidfuzz import fuzz

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

    for row in table.find_all("tr", {"class": lambda c: c and "sold" not in c}):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue

        product_name = cells[0].get_text(strip=True)
        console_cell = cells[1].get_text(strip=True) if len(cells) > 1 else ""

        # Score by name similarity + platform match
        name_score = fuzz.token_set_ratio(title_lower, product_name.lower())
        platform_bonus = 15 if console_lower and console_lower in console_cell.lower() else 0
        score = name_score + platform_bonus

        if score > best_score and score >= 55:
            # Try CIB price first (3rd column), then loose (2nd column)
            price = _parse_usd_cell(cells[2]) or (
                _parse_usd_cell(cells[1]) if len(cells) > 1 else None
            )
            if price:
                best_score = score
                best_price = price
                best_name = product_name

    return best_price, best_name


def _parse_product_page(soup: BeautifulSoup) -> tuple[float | None, str]:
    """Parse a direct product page when the search redirected to it."""
    title_el = soup.find("h1", {"id": "product_name"})
    product_name = title_el.get_text(strip=True) if title_el else ""

    # Look for CIB price in the price table
    for span in soup.find_all("span", {"class": "price"}):
        label = span.find_previous(string=re.compile(r'Complete|CIB|Loose', re.I))
        if label:
            price = _parse_usd_text(span.get_text(strip=True))
            if price:
                return price, product_name

    # Grab any price on the page
    price_el = soup.find("span", {"class": "price"})
    if price_el:
        price = _parse_usd_text(price_el.get_text(strip=True))
        if price:
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
```

- [ ] **Step 2: Verify import works**

```bash
python -c "from prices.pricecharting import PriceChartingPricer; p = PriceChartingPricer({}); print('OK')"
```

Expected: `[PriceCharting] Using web scraper.` then `OK`

---

### Task 3: Add scraper fallback to `prices/cardmarket.py`

**Files:**
- Modify: `prices/cardmarket.py`

When OAuth keys are missing, instead of returning `(None, "")` immediately, fall back to scraping `https://www.cardmarket.com/en/Pokemon/Products/Search?searchString={card_name}` to get the trend price from the first result's HTML.

- [ ] **Step 1: Add the `_scrape_fallback` method and update `__init__` and `get_price`**

Replace the `__init__` warning block:
```python
        if not self._enabled:
            logger.warning("[Cardmarket] No API credentials found — Pokemon prices will be skipped.")
```
With:
```python
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
```

Replace `get_price`:
```python
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
```

Add this new method to the `CardmarketPricer` class (before `_get_cached`):
```python
    def _scrape_fallback(self, name: str) -> tuple[float | None, str]:
        """Scrape Cardmarket search page for the trend price when API keys are missing."""
        from bs4 import BeautifulSoup

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

            # Each result card has a price element with class "price-container"
            # or the trend price in a <dd> following a <dt>Trend Price</dt>
            price = _extract_trend_price_from_search(soup)
            if price is None:
                return None, ""

            self._set_cached(cache_key, price)
            return price, f"Cardmarket trend scrape ({name})"

        except Exception as e:
            logger.warning(f"[Cardmarket] Scrape error for '{name}': {e}")
            return None, ""
```

Add this module-level helper function at the bottom of the file (after `_pick_best_product`):
```python
def _extract_trend_price_from_search(soup) -> float | None:
    """Extract the trend price from the first Cardmarket search result."""
    import re
    # Look for the first product's trend price in the search results
    # Cardmarket uses <span class="color-primary small"> for prices
    for el in soup.find_all(["span", "div"], class_=re.compile(r'price', re.I)):
        text = el.get_text(strip=True)
        # Match "45,99 €" or "45.99 €"
        match = re.search(r'([\d]+[,.][\d]{2})\s*€', text)
        if match:
            try:
                return float(match.group(1).replace(',', '.'))
            except ValueError:
                continue
    return None
```

- [ ] **Step 2: Verify import works**

```bash
python -c "from prices.cardmarket import CardmarketPricer; p = CardmarketPricer({}); print('OK')"
```

Expected: `[Cardmarket] No API credentials — using web scraper fallback.` then `OK`

---

### Task 4: Fix Leboncoin min_price bug

**Files:**
- Modify: `scrapers/leboncoin.py:43`

When both `min_price` and `max_price` are passed, the second `if` overwrites the price param with `min_price=0`.

- [ ] **Step 1: Fix the price parameter logic**

In `scrapers/leboncoin.py`, replace lines 39–43:
```python
        params = {"text": query}
        if min_price and min_price > 0:
            params["price"] = f"{int(min_price)}-max"
        if max_price:
            params["price"] = f"{int(min_price or 0)}-{int(max_price)}"
```
With:
```python
        params = {"text": query}
        if max_price:
            params["price"] = f"{int(min_price or 0)}-{int(max_price)}"
        elif min_price and min_price > 0:
            params["price"] = f"{int(min_price)}-max"
```

---

### Task 5: Align `TELEGRAM_BOT_TOKEN` in `main.py` and `bot.yml`

**Files:**
- Modify: `main.py:157`
- Modify: `.github/workflows/bot.yml:56`

The GitHub secret is named `TELEGRAM_BOT_TOKEN` (per CLAUDE.md), but the code reads `TELEGRAM_TOKEN`. Align them.

- [ ] **Step 1: Update `main.py` line 157**

Replace:
```python
    telegram_token = os.environ.get("TELEGRAM_TOKEN") or config["telegram"]["bot_token"]
```
With:
```python
    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_TOKEN") or config["telegram"]["bot_token"]
```

(Keeping `TELEGRAM_TOKEN` as a secondary fallback avoids breaking anything mid-migration.)

- [ ] **Step 2: Update `bot.yml` line 56 and remove unused secrets**

Replace the entire `env:` block in the `Run bot` step:
```yaml
        env:
          TELEGRAM_BOT_TOKEN:        ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID:          ${{ secrets.TELEGRAM_CHAT_ID }}
          CARDMARKET_APP_TOKEN:      ${{ secrets.CARDMARKET_APP_TOKEN }}
          CARDMARKET_APP_SECRET:     ${{ secrets.CARDMARKET_APP_SECRET }}
          CARDMARKET_ACCESS_TOKEN:   ${{ secrets.CARDMARKET_ACCESS_TOKEN }}
          CARDMARKET_ACCESS_SECRET:  ${{ secrets.CARDMARKET_ACCESS_SECRET }}
```

(Removed: `BRICKLINK_*` keys — replaced by scraper. Removed: `PRICECHARTING_API_KEY` — replaced by scraper.)

---

### Task 6: Create `get_chat_id.py`

**Files:**
- Create: `get_chat_id.py`

- [ ] **Step 1: Write the script**

```python
#!/usr/bin/env python3
"""
Helper script to find your Telegram Chat ID.

How to use:
  1. Open Telegram and send any message to your bot (press Start if first time)
  2. Run:  python get_chat_id.py
  3. Copy the Chat ID number shown
  4. Add it as TELEGRAM_CHAT_ID in GitHub → Settings → Secrets → Actions
"""

import os
import sys
import requests


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        token = input("Paste your TELEGRAM_BOT_TOKEN here: ").strip()

    if not token:
        print("ERROR: No token provided.")
        sys.exit(1)

    url = f"https://api.telegram.org/bot{token}/getUpdates"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
    except Exception as e:
        print(f"ERROR: Could not contact Telegram: {e}")
        sys.exit(1)

    if not data.get("ok"):
        print(f"ERROR: Telegram returned an error: {data.get('description', 'unknown')}")
        print("Make sure your bot token is correct.")
        sys.exit(1)

    results = data.get("result", [])
    if not results:
        print("No messages found yet.")
        print("→ Open Telegram, find your bot, and press START (or send any message).")
        print("→ Then run this script again.")
        sys.exit(0)

    # Extract unique chat IDs
    chats = {}
    for update in results:
        msg = update.get("message") or update.get("channel_post") or {}
        chat = msg.get("chat", {})
        chat_id = chat.get("id")
        chat_title = chat.get("title") or chat.get("username") or chat.get("first_name", "")
        if chat_id:
            chats[chat_id] = chat_title

    if not chats:
        print("Could not extract a chat ID from the updates.")
        sys.exit(1)

    print("\n" + "=" * 50)
    print("✅  Your Telegram Chat ID(s):")
    print("=" * 50)
    for chat_id, name in chats.items():
        print(f"  {chat_id}  ← {name}")
    print("=" * 50)
    print("\nCopy the number above, then add it as:")
    print("  GitHub → Settings → Secrets → Actions → New secret")
    print("  Name:  TELEGRAM_CHAT_ID")
    print(f"  Value: {list(chats.keys())[0]}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify the script runs without error**

```bash
python get_chat_id.py --help 2>&1 || python -c "import get_chat_id; print('imports OK')"
```

Expected: Script runs and prompts for token, or shows help.

---

## Self-Review

**Spec coverage check:**
- ✅ BrickLink → scraper (Task 1)
- ✅ PriceCharting → scraper (Task 2)
- ✅ Cardmarket → OAuth + scraper fallback (Task 3)
- ✅ Leboncoin bug fixed (Task 4)
- ✅ TELEGRAM_BOT_TOKEN aligned (Task 5)
- ✅ Unused secrets removed from bot.yml (Task 5)
- ✅ get_chat_id.py created (Task 6)
- ✅ requirements.txt already has beautifulsoup4 + lxml + rapidfuzz — no changes needed
- ✅ Vinted and Catawiki scrapers already working per codebase analysis — no changes needed

**Placeholder scan:** None found — all steps contain complete code.

**Type consistency:** `IdentifiedItem` imported consistently. `get_price` signature `(item: IdentifiedItem) -> tuple[float | None, str]` matches across all three pricers.
