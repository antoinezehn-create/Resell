"""
Item identifier — looks at a listing title and figures out:
  - What category it belongs to (Lego, Pokemon, Game)
  - Key identifiers (set number, card name, game title + platform)

This is the "brain" that maps raw listings to price lookups.
"""

import re
from dataclasses import dataclass, field
from enum import Enum


class ItemType(Enum):
    LEGO = "lego"
    POKEMON = "pokemon"
    GAME = "games"


@dataclass
class IdentifiedItem:
    type: ItemType
    raw_title: str
    # Lego specific
    set_number: str | None = None
    set_name: str | None = None
    # Pokemon specific
    card_name: str | None = None
    card_set: str | None = None
    # Game specific
    game_title: str | None = None
    platform: str | None = None
    extra: dict = field(default_factory=dict)

    def __str__(self):
        if self.type == ItemType.LEGO:
            return f"Lego {'#' + self.set_number if self.set_number else self.set_name}"
        elif self.type == ItemType.POKEMON:
            return f"Pokemon: {self.card_name or self.raw_title}"
        elif self.type == ItemType.GAME:
            return f"{self.platform or 'Game'}: {self.game_title or self.raw_title}"
        return self.raw_title


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Lego set numbers: 4–6 digits, not preceded/followed by another digit
LEGO_SET_PATTERN = re.compile(r'(?<!\d)(\d{4,6})(?!\d)')

# Lego keyword detection
LEGO_KEYWORDS = re.compile(
    r'\b(lego|l[eé]go|leggo|legos)\b', re.IGNORECASE
)

# Pokemon keyword detection
POKEMON_KEYWORDS = re.compile(
    r'\b(pok[eé]?mon|pokmon|pockemon|carte\s+pok|pok.{0,3}carte)\b',
    re.IGNORECASE
)
# Also catch standalone valuable card terms
POKEMON_CARD_TERMS = re.compile(
    r'\b(charizard|mewtwo|pikachu|blastoise|venusaur|lugia|rayquaza|'
    r'ho.?oh|umbreon|espeon|psa\s*\d|bgs\s*\d|base\s*set|'
    r'booster|display\s+pok|coffret\s+pok)\b',
    re.IGNORECASE
)

# Platform detection for retro games
PLATFORM_PATTERNS = {
    "SNES": re.compile(
        r'\b(snes|super\s+nintendo|super[\s-]nes|super\s+famicom)\b',
        re.IGNORECASE
    ),
    "N64": re.compile(
        r'\b(n64|nintendo\s*64)\b', re.IGNORECASE
    ),
    "Game Boy Advance": re.compile(
        r'\b(gba|game[\s-]?boy[\s-]?advance|gbas?p|game[\s-]?boy[\s-]?advance[\s-]?sp)\b',
        re.IGNORECASE
    ),
    "Game Boy Color": re.compile(
        r'\b(gbc|game[\s-]?boy[\s-]?color|game[\s-]?boy[\s-]?colour)\b',
        re.IGNORECASE
    ),
    "Game Boy": re.compile(
        r'\b(game[\s-]?boy|gameboy|gbp|game[\s-]?boy[\s-]?pocket)\b',
        re.IGNORECASE
    ),
}

# Noise words to strip when extracting clean names
NOISE_WORDS = re.compile(
    r'\b(complet|completé|avec|boite|boîte|notice|sans|neuf|occasion|'
    r'bon\s+état|très\s+bon|tbé|be|occasion|pal|ntsc|jeu|jeux|'
    r'cartouche|vendu|lot|ensemble|rare|vintage|retro|rétro|'
    r'collector|collection|sealed|scellé|blister)\b',
    re.IGNORECASE
)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def identify_item(title: str) -> IdentifiedItem | None:
    """
    Try to identify what a listing title refers to.
    Returns an IdentifiedItem or None if we can't classify it.
    """
    title_clean = title.strip()

    # --- Try Lego first ---
    if LEGO_KEYWORDS.search(title_clean):
        return _identify_lego(title_clean)

    # --- Try Pokemon ---
    if POKEMON_KEYWORDS.search(title_clean) or POKEMON_CARD_TERMS.search(title_clean):
        return _identify_pokemon(title_clean)

    # --- Try retro games ---
    for platform, pattern in PLATFORM_PATTERNS.items():
        if pattern.search(title_clean):
            return _identify_game(title_clean, platform)

    return None


# ---------------------------------------------------------------------------
# Lego identification
# ---------------------------------------------------------------------------

def _identify_lego(title: str) -> IdentifiedItem:
    # Look for set numbers in the title
    matches = LEGO_SET_PATTERN.findall(title)
    set_number = None

    for m in matches:
        num = int(m)
        # Valid Lego set number range (not a year, not a price like 1500)
        if 1000 <= num <= 99999 and num not in (2023, 2024, 2025, 2026):
            set_number = m
            break

    # Extract a clean name by removing lego keyword + noise
    clean = LEGO_KEYWORDS.sub("", title)
    clean = NOISE_WORDS.sub("", clean)
    # Remove the set number itself from name
    if set_number:
        clean = clean.replace(set_number, "")
    clean = re.sub(r'\s+', ' ', clean).strip(" -,")

    return IdentifiedItem(
        type=ItemType.LEGO,
        raw_title=title,
        set_number=set_number,
        set_name=clean if clean else None,
    )


# ---------------------------------------------------------------------------
# Pokemon identification
# ---------------------------------------------------------------------------

def _identify_pokemon(title: str) -> IdentifiedItem:
    # Try to extract a card name — remove Pokemon keyword and noise
    clean = POKEMON_KEYWORDS.sub("", title)
    clean = NOISE_WORDS.sub("", clean)
    clean = re.sub(r'\s+', ' ', clean).strip(" -,")

    # Try to detect the set
    card_set = None
    set_hints = {
        "Base Set": re.compile(r'\bbase\s*set\b|\bset\s+de\s+base\b', re.IGNORECASE),
        "Jungle": re.compile(r'\bjungle\b', re.IGNORECASE),
        "Fossil": re.compile(r'\bfossil\b', re.IGNORECASE),
        "Team Rocket": re.compile(r'\bteam\s+rocket\b', re.IGNORECASE),
        "Neo Genesis": re.compile(r'\bneo\s+genesis\b', re.IGNORECASE),
        "Hidden Fates": re.compile(r'\bhidden\s+fates\b', re.IGNORECASE),
        "Shiny Vault": re.compile(r'\bshiny\s+vault\b', re.IGNORECASE),
        "Celebrations": re.compile(r'\bcelebrations?\b', re.IGNORECASE),
        "Evolutions": re.compile(r'\bevolutions?\b', re.IGNORECASE),
        "Prismatic Evolutions": re.compile(r'\bprismatic\b', re.IGNORECASE),
    }
    for set_name, pattern in set_hints.items():
        if pattern.search(title):
            card_set = set_name
            break

    return IdentifiedItem(
        type=ItemType.POKEMON,
        raw_title=title,
        card_name=clean if clean else title,
        card_set=card_set,
    )


# ---------------------------------------------------------------------------
# Game identification
# ---------------------------------------------------------------------------

def _identify_game(title: str, platform: str) -> IdentifiedItem:
    # Remove platform name + noise to get the game title
    clean = title
    for p, pattern in PLATFORM_PATTERNS.items():
        clean = pattern.sub("", clean)
    clean = NOISE_WORDS.sub("", clean)
    clean = re.sub(r'\s+', ' ', clean).strip(" -,")

    return IdentifiedItem(
        type=ItemType.GAME,
        raw_title=title,
        game_title=clean if clean else title,
        platform=platform,
    )
