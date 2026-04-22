# Resell Bot — Claude Code Mission Brief

## Your Job

You are finishing and fixing this resell arbitrage bot. The user is non-technical. Your goal is to do as much as possible autonomously — write code, fix issues, replace broken APIs with scrapers — and only ask the user for things that genuinely require their input (credentials, clicking buttons in Telegram, etc.).

When something is blocked or paid, **don't stop — scrape instead.**

---

## What the Bot Does

Finds underpriced listings on second-hand marketplaces, checks real resale prices, sends Telegram alerts when profit margin ≥ 20% OR profit ≥ 50€.

**Marketplaces to scrape:** Vinted, Leboncoin, Catawiki
**Categories:** Lego sets, Pokémon cards, Retro games (SNES, N64, GameBoy/Color/Advance, PAL)
**Runs:** Every 30 minutes via GitHub Actions free tier (no server needed)

---

## File Structure

```
resell-bot/
├── main.py                  ← orchestrator
├── config.yml               ← thresholds, themes, watchlist
├── seen.json                ← already-notified listings (prune >7 days)
├── requirements.txt
├── scrapers/
│   ├── vinted.py
│   ├── leboncoin.py
│   └── catawiki.py
├── prices/
│   ├── bricklink.py
│   ├── cardmarket.py
│   └── pricecharting.py
├── utils/
│   ├── keywords.py          ← 635 keywords + misspellings
│   ├── matcher.py           ← identifies item from title
│   └── database.py          ← seen.json read/write/prune
├── notifier/
│   └── telegram.py
└── .github/workflows/bot.yml
```

---

## API Problems — Fix With Scrapers

These APIs are blocked or paid. Do NOT wait for the user to unlock them. Rewrite the relevant price modules to scrape the website instead.

### BrickLink → scrape the website
- **Problem:** API requires a seller account with ≥1 buyer feedback. User doesn't have that yet.
- **Fix:** Rewrite `prices/bricklink.py` to scrape `https://www.bricklink.com/v2/catalog/catalogitem.page?S={set_number}-1` and extract the average 6-month sales price from the page HTML. Use `requests` + `BeautifulSoup`. Cache results 24h in a local JSON file to avoid hammering the site.
- If BrickLink blocks scraping, fall back to scraping `https://www.brick-economy.com/set/{set_number}` which is more scraper-friendly.

### PriceCharting → scrape the website
- **Problem:** Official API is paid (PriceCharting Pro). Not free.
- **Fix:** Rewrite `prices/pricecharting.py` to scrape `https://www.pricecharting.com/search-products?q={game_title}&type=videogames` and extract the loose / CIB / graded price from the HTML. Use `requests` + `BeautifulSoup`. Cache 24h.
- Match the game title carefully (fuzzy match if needed using `difflib`).

### Cardmarket → keep OAuth1 API, but make it optional
- API works fine with a Private Account (free signup, no business docs needed).
- Keep `prices/cardmarket.py` as-is with OAuth1.
- If keys are missing from environment, **fall back to scraping** `https://www.cardmarket.com/en/Pokemon/Products/Search?searchString={card_name}` to get the trend price.

---

## What Needs Scraping (Marketplace Side)

All three marketplace scrapers already exist but may need fixing. Verify each one works:

### Vinted
- Use the unofficial Vinted API: `https://www.vinted.fr/api/v2/catalog/items?search_text={keyword}&per_page=20`
- Requires setting a `Cookie` header with a valid Vinted session cookie.
- If the current implementation is broken, rewrite to fetch a fresh session cookie from `https://www.vinted.fr` first, then use it for search requests.

### Leboncoin
- Scrape `https://www.leboncoin.fr/recherche?text={keyword}&locations=` using the `__NEXT_DATA__` JSON embedded in the page HTML.
- Parse `window.__NEXT_DATA__` → `props.pageProps.searchData.ads`
- If that path changed, fall back to parsing `<script id="__NEXT_DATA__">` tag content directly.

### Catawiki
- Use the buyer search API: `https://www.catawiki.com/buyer/api/v1/lots?query={keyword}`
- If blocked, scrape the HTML search results page instead.

---

## Telegram Setup

The user has a Telegram bot token. The only thing they need to do manually is:
1. Open Telegram → find their bot → press Start
2. Tell you their token so you can fetch the Chat ID automatically

**Write a helper script** `get_chat_id.py` that:
- Takes `TELEGRAM_BOT_TOKEN` from environment or asks the user to paste it
- Calls `https://api.telegram.org/bot{TOKEN}/getUpdates`
- Prints the Chat ID clearly

Then tell the user: "Run `python get_chat_id.py`, copy the number it shows, add it as `TELEGRAM_CHAT_ID` in GitHub Secrets."

---

## GitHub Actions

`bot.yml` must:
- Run on `schedule: cron: '*/30 * * * *'`
- Also support manual trigger: `workflow_dispatch`
- Install dependencies from `requirements.txt`
- Pass all secrets as environment variables to `main.py`
- On failure, send a Telegram message saying "⚠️ Bot crashed — check Actions logs"

---

## GitHub Secrets the User Must Add

Minimize this list. Only ask for what's truly needed. Tell the user exactly where to go (Settings → Secrets → Actions) and what to name each one.

**Required now:**
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

**Optional (Cardmarket, for better Pokémon prices):**
- `CARDMARKET_APP_TOKEN`
- `CARDMARKET_APP_SECRET`
- `CARDMARKET_ACCESS_TOKEN`
- `CARDMARKET_ACCESS_SECRET`

**Skip entirely:**
- BrickLink keys (scraper handles it)
- PriceCharting key (scraper handles it)

---

## Rules

- User is non-technical. Never ask them to write code or edit files manually.
- Free tier only. No paid APIs, no paid services.
- If an API is blocked or paid → scrape instead.
- Cache all price lookups for 24h to avoid rate limits.
- Only ping the user when you genuinely need a credential or a click in a UI.
- When done, give the user a clear checklist of the 3-5 things they need to do (add secrets, press Start on Telegram, etc.).
- Write clean, readable Python with comments explaining what each part does.

---

## Start Here

1. Read all existing files in the repo
2. Identify what's broken or incomplete
3. Fix `prices/bricklink.py` and `prices/pricecharting.py` to use scrapers
4. Add scraper fallbacks to `prices/cardmarket.py`
5. Verify all three marketplace scrapers work
6. Write `get_chat_id.py`
7. Verify `bot.yml` is correct
8. Update `requirements.txt` with any new dependencies (e.g. `beautifulsoup4`, `lxml`)
9. Give the user a final checklist of exactly what they need to do to go live
