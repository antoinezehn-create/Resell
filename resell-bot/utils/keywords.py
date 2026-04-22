"""
Keyword generator for all three product categories.

Strategy:
- Include correct spellings, common misspellings, French variants, accent variations
- For Lego: focus on best-resale themes + high-value set numbers
- For Pokemon: card sets, popular card names, product types
- For Games: all platform names/abbreviations + common French search terms
"""


def get_all_keywords(config: dict) -> dict:
    """Return a dict with 'lego', 'pokemon', 'games' keyword lists."""
    return {
        "lego": _lego_keywords(config),
        "pokemon": _pokemon_keywords(),
        "games": _game_keywords(),
    }


# ---------------------------------------------------------------------------
# LEGO
# ---------------------------------------------------------------------------

def _lego_keywords(config: dict) -> list[str]:
    themes = config.get("search", {}).get("lego_themes", [])
    watchlist = config.get("search", {}).get("lego_watchlist_sets", [])

    # Base word variants (covers misspellings + accents)
    base = ["lego", "légo", "légos", "legos", "leggo", "l3go"]

    # Theme search terms — each paired with base variants
    theme_terms = {
        "star_wars": [
            "star wars", "starwars", "star-wars",
            "millenium falcon", "millennium falcon",
            "at-at", "at at", "atat",
            "death star", "x-wing", "xwing",
        ],
        "technic": ["technic", "técnic", "technik"],
        "icons": [
            "icons", "creator expert", "creator-expert",
            "eiffel", "colosseum", "colisée", "colisee",
        ],
        "harry_potter": [
            "harry potter", "harry-potter",
            "poudlard", "hogwarts",
        ],
        "creator_expert": ["creator expert", "creator-expert"],
        "ideas": ["ideas", "idées", "idees"],
        "architecture": ["architecture"],
        "speed_champions": [
            "speed champions", "speed-champions",
            "ferrari", "lamborghini", "mclaren",
        ],
        "exclusives": [
            "sdcc", "exclusive", "exclusif",
            "vip", "gwp",
        ],
    }

    keywords = set()

    # Always add set numbers from watchlist directly
    for set_no in watchlist:
        keywords.add(set_no)
        # Also pair with base to catch "lego 75192" style listings
        for b in ["lego", "légo"]:
            keywords.add(f"{b} {set_no}")

    # Add theme combinations
    for theme, terms in theme_terms.items():
        if not themes or theme in themes:
            for b in base:
                for term in terms:
                    keywords.add(f"{b} {term}")

    # Add bare base words to catch any Lego listing
    for b in base:
        keywords.add(b)

    return sorted(keywords)


# ---------------------------------------------------------------------------
# POKEMON
# ---------------------------------------------------------------------------

def _pokemon_keywords() -> list[str]:
    keywords = set()

    # Name variants (misspellings + accent)
    name_variants = [
        "pokemon", "pokémon", "pokmon", "pokémons", "pokemons",
        "pockemon", "pokkemon", "pokéeman",
    ]

    # French search patterns
    fr_terms = [
        "carte", "cartes", "card", "cards",
        "booster", "display", "coffret",
        "etb", "elite trainer",
        "collection", "deck",
    ]

    for name in name_variants:
        keywords.add(name)
        for term in fr_terms:
            keywords.add(f"{name} {term}")
            keywords.add(f"{term} {name}")

    # Valuable card names / sets that often appear in titles
    valuable = [
        # Vintage sets
        "base set", "set de base", "jungle set", "fossil",
        "team rocket", "neo genesis", "neo discovery",
        "gym heroes", "gym challenge",
        # Popular card names
        "charizard", "pikachu holo", "mewtwo", "blastoise", "venusaur",
        "lugia", "ho-oh", "rayquaza",
        # Modern chase cards
        "charizard vmax", "pikachu vmax", "umbreon vmax",
        "alt art", "alternate art", "gold card", "carte gold",
        "psa", "bgs", "cgc",  # graded cards
        # Sets
        "evolutions", "celebrations",
        "hidden fates", "shiny vault",
        "prismatic evolutions",
    ]

    for term in valuable:
        keywords.add(term)
        for name in ["pokemon", "pokémon"]:
            keywords.add(f"{name} {term}")

    return sorted(keywords)


# ---------------------------------------------------------------------------
# RETRO GAMES
# ---------------------------------------------------------------------------

def _game_keywords() -> list[str]:
    keywords = set()

    platform_variants = {
        "SNES": [
            "snes", "super nintendo", "super nes", "super-nes",
            "super famicom", "super famicom pal",
            "jeu snes", "jeux snes", "jeu super nintendo",
            "cartouche snes", "cartouche super nintendo",
        ],
        "N64": [
            "n64", "nintendo 64", "nintendo64", "nintendo-64",
            "jeu n64", "jeux n64", "jeu nintendo 64",
            "cartouche n64",
        ],
        "GameBoy": [
            "game boy", "gameboy", "game-boy", "gb jeu",
            "jeu game boy", "jeux game boy",
            "cartouche gameboy", "cartouche game boy",
        ],
        "GameBoyColor": [
            "game boy color", "gameboy color", "gbc",
            "jeu gbc", "jeu game boy color",
        ],
        "GameBoyAdvance": [
            "game boy advance", "gameboy advance", "gba",
            "jeu gba", "jeu game boy advance",
            "game boy advance sp", "gba sp",
        ],
        "GameBoyPocket": [
            "game boy pocket", "gbp",
        ],
    }

    # Popular/valuable titles that often appear alone without platform name
    valuable_titles = [
        # SNES
        "zelda link past", "super metroid", "super mario world",
        "super mario kart", "earthbound", "final fantasy",
        "chrono trigger", "street fighter",
        "donkey kong country",
        # N64
        "zelda ocarina", "zelda majoras", "super mario 64",
        "mario kart 64", "goldeneye", "banjo kazooie",
        "paper mario", "conker",
        # GameBoy / GBA
        "pokemon rouge", "pokemon bleu", "pokemon vert",
        "pokemon rouge feu", "pokemon saphir", "pokemon rubis",
        "zelda oracle", "zelda awakening",
        "castlevania", "metroid fusion", "fire emblem",
        "mother 3",
    ]

    for platform, terms in platform_variants.items():
        for term in terms:
            keywords.add(term)

    for title in valuable_titles:
        keywords.add(title)

    # Also add "PAL" combos for the main platforms
    for p in ["snes", "n64", "gameboy", "gba", "gbc"]:
        keywords.add(f"{p} pal")
        keywords.add(f"jeu {p}")
        keywords.add(f"jeux {p}")

    return sorted(keywords)
