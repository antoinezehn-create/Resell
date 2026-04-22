"""
Telegram notifier — sends nicely formatted deal alerts to your chat.

Uses the Bot API directly (no extra library needed for simple sends).
Format example:

  🔥 DEAL — Vinted
  🧱 Lego Millennium Falcon #75192

  💰 Listed:    350 €
  📊 Market:    520 € (BrickLink avg sold)
  💵 Profit:    +170 € (+33%)

  🔗 https://www.vinted.fr/items/...
"""

import logging
import requests

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"

# Emojis per platform
PLATFORM_EMOJI = {
    "Vinted": "👗",
    "Leboncoin": "🏷️",
    "Catawiki": "🎪",
}

# Emojis per item type
CATEGORY_EMOJI = {
    "lego": "🧱",
    "pokemon": "🃏",
    "games": "🎮",
}


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str):
        self._token = token
        self._chat_id = chat_id
        self._url = TELEGRAM_API.format(token=token)
        self._enabled = bool(token and chat_id)

        if not self._enabled:
            logger.warning("[Telegram] No token/chat_id — notifications disabled.")

    def send_deal(
        self,
        listing: dict,
        item,
        listing_price: float,
        reference_price: float,
        profit: float,
        margin: float,
        price_source: str,
    ):
        if not self._enabled:
            return

        platform = listing.get("platform", "?")
        platform_emoji = PLATFORM_EMOJI.get(platform, "🛒")
        category_emoji = CATEGORY_EMOJI.get(item.type.value, "📦")

        # Deal quality label
        if margin >= 40 or profit >= 200:
            quality = "🔥🔥 GROS DEAL"
        elif margin >= 25 or profit >= 100:
            quality = "🔥 BON DEAL"
        else:
            quality = "✅ DEAL"

        title_display = str(item)

        text = (
            f"{quality} — {platform_emoji} {platform}\n"
            f"{category_emoji} {title_display}\n"
            f"\n"
            f"💰 Prix affiché : <b>{listing_price:.0f} €</b>\n"
            f"📊 Prix marché  : {reference_price:.0f} € ({price_source})\n"
            f"💵 Bénéfice     : <b>+{profit:.0f} € (+{margin:.0f}%)</b>\n"
        )

        # Add description snippet if available
        desc = listing.get("description", "").strip()
        if desc:
            text += f"\n📝 {desc[:150]}{'...' if len(desc) > 150 else ''}\n"

        text += f"\n🔗 {listing.get('url', '')}"

        self._send(text)
        logger.info(f"[Telegram] Alert sent: {title_display} +{profit:.0f}€")

    def send_startup_message(self, n_keywords: int):
        """Send a message when the bot starts a new run."""
        if not self._enabled:
            return
        self._send(
            f"🤖 Bot démarré — scan de {n_keywords} mots-clés "
            f"sur Vinted, Leboncoin et Catawiki."
        )

    def send_summary(self, n_listings: int, n_deals: int):
        """Send a brief summary at the end of each run (optional)."""
        if not self._enabled or n_deals == 0:
            return
        self._send(
            f"✅ Scan terminé — {n_listings} annonces analysées, "
            f"{n_deals} deal(s) trouvé(s)."
        )

    def _send(self, text: str):
        try:
            resp = requests.post(
                self._url,
                json={
                    "chat_id": self._chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": False,
                },
                timeout=10,
            )
            if resp.status_code != 200:
                logger.warning(f"[Telegram] Send failed: {resp.status_code} — {resp.text[:200]}")
        except requests.RequestException as e:
            logger.warning(f"[Telegram] Request error: {e}")
