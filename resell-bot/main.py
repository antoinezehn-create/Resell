#!/usr/bin/env python3
"""
Resell Bot — Main orchestrator.

Flow per run:
  1. Load config & init all components
  2. For each marketplace × each keyword category → fetch listings
  3. For each new listing → identify item type → fetch reference price
  4. If deal threshold met → send Telegram alert
  5. Save seen-listing IDs to seen.json (committed back to repo by GitHub Actions)

Run manually:  python main.py
Run via cloud: GitHub Actions calls this automatically every 30 min (free).
"""

import os
import time
import logging
import yaml

from scrapers.vinted import VintedScraper
from scrapers.leboncoin import LeboncoinScraper
from scrapers.catawiki import CatawiKiScraper
from prices.bricklink import BrickLinkPricer
from prices.cardmarket import CardmarketPricer
from prices.pricecharting import PriceChartingPricer
from utils.keywords import get_all_keywords
from utils.matcher import identify_item, ItemType
from utils.database import SeenListings
from notifier.telegram import TelegramNotifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config() -> dict:
    with open("config.yml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Deal check
# ---------------------------------------------------------------------------

def is_a_deal(listing_price: float, reference_price: float, config: dict) -> bool:
    """
    Return True if the listing qualifies as a deal:
      - Margin >= min_margin_percent (default 20%), OR
      - Profit >= min_profit_euros (default 50€)
    """
    if reference_price is None or reference_price <= 0:
        return False
    profit = reference_price - listing_price
    if profit <= 0:
        return False
    margin = profit / reference_price
    min_margin = config["alerts"]["min_margin_percent"] / 100.0
    min_profit = config["alerts"]["min_profit_euros"]
    return margin >= min_margin or profit >= min_profit


# ---------------------------------------------------------------------------
# Per-listing processor
# ---------------------------------------------------------------------------

def process_listing(
    listing: dict,
    config: dict,
    pricers: dict,
    notifier: TelegramNotifier,
    seen: SeenListings,
) -> bool:
    """Process one listing. Returns True if a deal was found."""
    listing_id = listing["id"]

    if seen.has_seen(listing_id):
        return False

    # Always mark as seen so we don't re-process even if price lookup fails
    seen.mark_seen(listing_id)

    title = listing["title"]
    price = listing["price"]

    if not title or price is None:
        return False

    # Identify what this listing is about
    item = identify_item(title)
    if item is None:
        return False

    # Check minimum price threshold for this category
    min_prices = config["alerts"]["min_prices"]
    min_price = min_prices.get(item.type.value, 5)
    if price < min_price:
        return False

    # Fetch reference price
    reference_price = None
    price_source = ""

    try:
        if item.type == ItemType.LEGO:
            reference_price, price_source = pricers["bricklink"].get_price(item)
        elif item.type == ItemType.POKEMON:
            reference_price, price_source = pricers["cardmarket"].get_price(item)
        elif item.type == ItemType.GAME:
            reference_price, price_source = pricers["pricecharting"].get_price(item)
    except Exception as e:
        logger.debug(f"Price lookup error for '{title}': {e}")
        return False

    if not reference_price:
        return False

    # Check deal threshold
    if not is_a_deal(price, reference_price, config):
        return False

    profit = reference_price - price
    margin = (profit / reference_price) * 100

    logger.info(
        f"DEAL  {listing['platform']:12}  {price:.0f}€ → {reference_price:.0f}€  "
        f"+{profit:.0f}€ (+{margin:.0f}%)  [{title[:60]}]"
    )

    notifier.send_deal(
        listing=listing,
        item=item,
        listing_price=price,
        reference_price=reference_price,
        profit=profit,
        margin=margin,
        price_source=price_source,
    )
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run():
    config = load_config()

    # Override config values with environment variables when running in GitHub Actions
    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_TOKEN") or config["telegram"]["bot_token"]
    telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID") or config["telegram"]["chat_id"]

    scrapers = [
        VintedScraper(),
        LeboncoinScraper(),
        CatawiKiScraper(),
    ]

    pricers = {
        "bricklink":     BrickLinkPricer(config.get("bricklink", {})),
        "cardmarket":    CardmarketPricer(config.get("cardmarket", {})),
        "pricecharting": PriceChartingPricer(config.get("pricecharting", {})),
    }

    notifier = TelegramNotifier(token=telegram_token, chat_id=telegram_chat_id)
    seen = SeenListings()
    keywords = get_all_keywords(config)

    total_keywords = sum(len(v) for v in keywords.values())
    logger.info(f"Bot started — {total_keywords} keywords across 3 categories")

    min_prices = config["alerts"]["min_prices"]
    total_listings = 0
    total_deals = 0

    for scraper in scrapers:
        logger.info(f"--- Scraping {scraper.name} ---")
        seen_in_this_run: set[str] = set()
        all_listings: list[dict] = []

        # Lego
        for kw in keywords["lego"]:
            try:
                results = scraper.search(kw, min_price=min_prices["lego"])
                all_listings.extend(results)
                time.sleep(0.4)
            except Exception as e:
                logger.debug(f"[{scraper.name}] '{kw}' error: {e}")

        # Pokemon
        for kw in keywords["pokemon"]:
            try:
                results = scraper.search(kw, min_price=min_prices["pokemon"])
                all_listings.extend(results)
                time.sleep(0.4)
            except Exception as e:
                logger.debug(f"[{scraper.name}] '{kw}' error: {e}")

        # Games
        for kw in keywords["games"]:
            try:
                results = scraper.search(kw, min_price=min_prices["games"])
                all_listings.extend(results)
                time.sleep(0.4)
            except Exception as e:
                logger.debug(f"[{scraper.name}] '{kw}' error: {e}")

        # Deduplicate within this scraper run
        unique = []
        for listing in all_listings:
            lid = listing["id"]
            if lid not in seen_in_this_run:
                seen_in_this_run.add(lid)
                unique.append(listing)

        logger.info(f"[{scraper.name}] {len(unique)} unique listings to check")
        total_listings += len(unique)

        for listing in unique:
            try:
                found = process_listing(listing, config, pricers, notifier, seen)
                if found:
                    total_deals += 1
            except Exception as e:
                logger.debug(f"process_listing error: {e}")

    # Persist seen listings
    seen.save()

    logger.info(
        f"Run complete — {total_listings} listings checked, "
        f"{total_deals} deal(s) found"
    )

    # Send summary only if deals were found
    notifier.send_summary(total_listings, total_deals)


if __name__ == "__main__":
    run()
