"""
Tracks listing IDs we've already processed so we never send
the same deal alert twice.

Storage: a simple JSON file (seen.json) committed back to the
GitHub repo after each run. Entries older than 30 days are
pruned automatically to keep the file small.
"""

import json
import os
import time
from pathlib import Path

DB_PATH = Path("seen.json")
EXPIRY_DAYS = 30


class SeenListings:
    def __init__(self):
        self._data: dict[str, float] = {}  # id -> unix timestamp when first seen
        self._load()

    def _load(self):
        if DB_PATH.exists():
            try:
                with open(DB_PATH, "r") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._data = {}
        self._prune()

    def _prune(self):
        """Remove entries older than EXPIRY_DAYS."""
        cutoff = time.time() - EXPIRY_DAYS * 86400
        before = len(self._data)
        self._data = {k: v for k, v in self._data.items() if v > cutoff}
        pruned = before - len(self._data)
        if pruned:
            print(f"[DB] Pruned {pruned} old entries from seen.json")

    def has_seen(self, listing_id: str) -> bool:
        return listing_id in self._data

    def mark_seen(self, listing_id: str):
        self._data[listing_id] = time.time()

    def save(self):
        with open(DB_PATH, "w") as f:
            json.dump(self._data, f, indent=2)
        print(f"[DB] Saved {len(self._data)} seen listings to seen.json")
