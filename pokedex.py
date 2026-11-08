"""Pokédex catch system for Fischer Chess.

Every solved puzzle catches one Gen 1 Pokémon. Harder puzzles (by tactic type) and
first-try solves give better odds at rare and legendary Pokémon. Duplicates are kept
(counted), so kids can trade extras later.
"""

import random
import sqlite3
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

# "Today" for the daily egg is the family's local day, not the server's UTC day.
LOCAL_TZ = ZoneInfo("America/Los_Angeles")

NAMES = [
    'Bulbasaur', 'Ivysaur', 'Venusaur', 'Charmander', 'Charmeleon', 'Charizard', 'Squirtle',
    'Wartortle', 'Blastoise', 'Caterpie', 'Metapod', 'Butterfree', 'Weedle', 'Kakuna',
    'Beedrill', 'Pidgey', 'Pidgeotto', 'Pidgeot', 'Rattata', 'Raticate', 'Spearow', 'Fearow',
    'Ekans', 'Arbok', 'Pikachu', 'Raichu', 'Sandshrew', 'Sandslash', 'Nidoran♀', 'Nidorina',
    'Nidoqueen', 'Nidoran♂', 'Nidorino', 'Nidoking', 'Clefairy', 'Clefable', 'Vulpix',
    'Ninetales', 'Jigglypuff', 'Wigglytuff', 'Zubat', 'Golbat', 'Oddish', 'Gloom', 'Vileplume',
    'Paras', 'Parasect', 'Venonat', 'Venomoth', 'Diglett', 'Dugtrio', 'Meowth', 'Persian',
    'Psyduck', 'Golduck', 'Mankey', 'Primeape', 'Growlithe', 'Arcanine', 'Poliwag',
    'Poliwhirl', 'Poliwrath', 'Abra', 'Kadabra', 'Alakazam', 'Machop', 'Machoke', 'Machamp',
    'Bellsprout', 'Weepinbell', 'Victreebel', 'Tentacool', 'Tentacruel', 'Geodude', 'Graveler',
    'Golem', 'Ponyta', 'Rapidash', 'Slowpoke', 'Slowbro', 'Magnemite', 'Magneton',
    "Farfetch'd", 'Doduo', 'Dodrio', 'Seel', 'Dewgong', 'Grimer', 'Muk', 'Shellder',
    'Cloyster', 'Gastly', 'Haunter', 'Gengar', 'Onix', 'Drowzee', 'Hypno', 'Krabby', 'Kingler',
    'Voltorb', 'Electrode', 'Exeggcute', 'Exeggutor', 'Cubone', 'Marowak', 'Hitmonlee',
    'Hitmonchan', 'Lickitung', 'Koffing', 'Weezing', 'Rhyhorn', 'Rhydon', 'Chansey', 'Tangela',
    'Kangaskhan', 'Horsea', 'Seadra', 'Goldeen', 'Seaking', 'Staryu', 'Starmie', 'Mr. Mime',
    'Scyther', 'Jynx', 'Electabuzz', 'Magmar', 'Pinsir', 'Tauros', 'Magikarp', 'Gyarados',
    'Lapras', 'Ditto', 'Eevee', 'Vaporeon', 'Jolteon', 'Flareon', 'Porygon', 'Omanyte',
    'Omastar', 'Kabuto', 'Kabutops', 'Aerodactyl', 'Snorlax', 'Articuno', 'Zapdos', 'Moltres',
    'Dratini', 'Dragonair', 'Dragonite', 'Mewtwo', 'Mew',
]
TOTAL = len(NAMES)  # 151

LEGENDARY = {144, 145, 146, 150, 151}
RARE = {3, 6, 9, 59, 65, 68, 94, 113, 115, 123, 128, 130, 131, 132, 133, 134, 135, 136, 137,
        142, 143, 147, 148, 149}
UNCOMMON = {2, 5, 8, 12, 15, 18, 20, 22, 24, 25, 26, 28, 31, 34, 36, 38, 40, 42, 45, 47, 49,
            51, 53, 55, 57, 62, 64, 67, 71, 73, 76, 78, 80, 82, 83, 85, 87, 89, 91, 93, 95, 97,
            99, 101, 103, 105, 106, 107, 108, 110, 112, 114, 117, 119, 121, 122, 124, 125, 126,
            127, 139, 141}
COMMON = set(range(1, TOTAL + 1)) - LEGENDARY - RARE - UNCOMMON

RARITY_POOLS = {"common": COMMON, "uncommon": UNCOMMON, "rare": RARE, "legendary": LEGENDARY}
RARITY_ORDER = ["common", "uncommon", "rare", "legendary"]

# Odds (%) of each rarity, indexed by puzzle difficulty 0-3.
FIRST_TRY_ODDS = [
    (80, 18, 2, 0),   # 0: positional / plain capture or check
    (60, 32, 7, 1),   # 1: one real tactic (fork, pin, skewer, trapped piece, promotion)
    (45, 38, 14, 3),  # 2: discovered attack, or a combination of tactics
    (30, 40, 24, 6),  # 3: checkmate
]
RETRY_ODDS = (85, 15, 0, 0)

# When rolling inside a rarity pool, chance to prefer a Pokémon the kid hasn't caught yet.
PREFER_NEW = 0.5

_HARD = {"fork", "pin", "skewer", "trapped piece", "promotion"}
_HARDER = {"discovered attack", "discovered check"}
_MATE = {"checkmate", "back rank mate", "smothered mate"}


def rarity_of(pokemon_id):
    for r in RARITY_ORDER:
        if pokemon_id in RARITY_POOLS[r]:
            return r
    return "common"


def sprite(pokemon_id):
    return f"/static/pokedex/{pokemon_id}.png"


def difficulty(tactics_csv):
    """Map a puzzle's comma-separated tactic labels to difficulty 0-3."""
    tags = {t.strip() for t in (tactics_csv or "").split(",") if t.strip()}
    if tags & _MATE:
        return 3
    real = tags & (_HARD | _HARDER)
    if tags & _HARDER or len(real) >= 2:
        return 2
    if real:
        return 1
    return 0


def roll(tactics_csv, first_try, caught_ids, rng=random):
    """Pick a Pokémon id for a solve. Returns (pokemon_id, rarity)."""
    odds = FIRST_TRY_ODDS[difficulty(tactics_csv)] if first_try else RETRY_ODDS
    rarity = rng.choices(RARITY_ORDER, weights=odds, k=1)[0]
    pool = sorted(RARITY_POOLS[rarity])
    unseen = [p for p in pool if p not in caught_ids]
    if unseen and rng.random() < PREFER_NEW:
        pool = unseen
    return rng.choice(pool), rarity


def catch_for_puzzle(conn, user_id, puzzle_id, first_try):
    """Catch a Pokémon for a solved puzzle. At most one catch per puzzle.

    Returns a dict describing the catch, or None if this puzzle already caught one.
    Caller commits.
    """
    if conn.execute("SELECT 1 FROM pokedex_catches WHERE user_id = ? AND puzzle_id = ?",
                    (user_id, puzzle_id)).fetchone():
        return None
    row = conn.execute("SELECT tactics FROM puzzles WHERE id = ?", (puzzle_id,)).fetchone()
    tactics = row[0] if row else ""
    caught = {r[0] for r in conn.execute(
        "SELECT DISTINCT pokemon_id FROM pokedex_catches WHERE user_id = ?", (user_id,))}
    pid, rarity = roll(tactics, first_try, caught)
    conn.execute("INSERT INTO pokedex_catches (user_id, pokemon_id, puzzle_id) VALUES (?, ?, ?)",
                 (user_id, pid, puzzle_id))
    return {"id": pid, "name": NAMES[pid - 1], "rarity": rarity, "image": sprite(pid),
            "new": pid not in caught}


def unique_caught(conn, user_id):
    return conn.execute("SELECT COUNT(DISTINCT pokemon_id) FROM pokedex_catches WHERE user_id = ?",
                        (user_id,)).fetchone()[0]


def get_pokedex(conn, user_id):
    """All 151 entries with how many of each the user has caught."""
    counts = {r[0]: r[1] for r in conn.execute(
        "SELECT pokemon_id, COUNT(*) FROM pokedex_catches WHERE user_id = ? GROUP BY pokemon_id",
        (user_id,))}
    entries = [{"id": i, "name": NAMES[i - 1], "rarity": rarity_of(i), "image": sprite(i),
                "count": counts.get(i, 0)} for i in range(1, TOTAL + 1)]
    return {"entries": entries, "unique": len(counts), "total_caught": sum(counts.values()),
            "total": TOTAL}


# --- Daily egg -------------------------------------------------------------------------
# One egg per local day. It hatches on the first puzzle solved that day. Consecutive days
# build an egg streak: longer streaks give better odds, and every 7th day is a guaranteed
# rare-or-legendary.

EGG_GUARANTEE_EVERY = 7


def egg_odds(streak):
    if streak % EGG_GUARANTEE_EVERY == 0:
        return (0, 0, 85, 15)
    if streak >= EGG_GUARANTEE_EVERY:
        return (40, 38, 18, 4)
    if streak >= 3:
        return (50, 35, 13, 2)
    return (70, 25, 5, 0)


def local_today():
    return datetime.now(LOCAL_TZ).date()


def _egg_streak_ending(conn, user_id, last_day):
    """Number of consecutive egg days ending on last_day (inclusive)."""
    days = {date.fromisoformat(r[0]) for r in conn.execute(
        "SELECT day FROM daily_eggs WHERE user_id = ? AND day <= ? ORDER BY day DESC LIMIT 400",
        (user_id, last_day.isoformat()))}
    streak, d = 0, last_day
    while d in days:
        streak += 1
        d -= timedelta(days=1)
    return streak


def egg_status(conn, user_id, today=None):
    today = today or local_today()
    row = conn.execute("SELECT pokemon_id FROM daily_eggs WHERE user_id = ? AND day = ?",
                       (user_id, today.isoformat())).fetchone()
    if row:
        streak = _egg_streak_ending(conn, user_id, today)
        pid = row[0]
        hatched = {"id": pid, "name": NAMES[pid - 1], "rarity": rarity_of(pid), "image": sprite(pid)}
    else:
        # Streak the kid will be on once today's egg hatches.
        streak = _egg_streak_ending(conn, user_id, today - timedelta(days=1)) + 1
        hatched = None
    next_day = streak + 1 if hatched else streak
    days_to_guarantee = (-next_day) % EGG_GUARANTEE_EVERY
    return {"hatched": hatched, "streak": streak,
            "guaranteed_today": hatched is None and streak % EGG_GUARANTEE_EVERY == 0,
            "days_to_guarantee": days_to_guarantee}


def hatch_daily_egg(conn, user_id, today=None, rng=random):
    """Hatch today's egg if it hasn't hatched yet. Caller commits. Returns the hatch or None."""
    today = today or local_today()
    if conn.execute("SELECT 1 FROM daily_eggs WHERE user_id = ? AND day = ?",
                    (user_id, today.isoformat())).fetchone():
        return None
    streak = _egg_streak_ending(conn, user_id, today - timedelta(days=1)) + 1
    rarity = rng.choices(RARITY_ORDER, weights=egg_odds(streak), k=1)[0]
    caught = {r[0] for r in conn.execute(
        "SELECT DISTINCT pokemon_id FROM pokedex_catches WHERE user_id = ?", (user_id,))}
    pool = sorted(RARITY_POOLS[rarity])
    unseen = [p for p in pool if p not in caught]
    if unseen and rng.random() < PREFER_NEW:
        pool = unseen
    pid = rng.choice(pool)
    try:
        conn.execute("INSERT INTO daily_eggs (user_id, day, pokemon_id) VALUES (?, ?, ?)",
                     (user_id, today.isoformat(), pid))
    except sqlite3.IntegrityError:
        return None  # another request hatched it a moment ago
    # puzzle_id NULL: an egg catch, not tied to a puzzle (NULLs don't collide on the unique key).
    conn.execute("INSERT INTO pokedex_catches (user_id, pokemon_id, puzzle_id) VALUES (?, ?, NULL)",
                 (user_id, pid))
    return {"id": pid, "name": NAMES[pid - 1], "rarity": rarity, "image": sprite(pid),
            "new": pid not in caught, "streak": streak,
            "guaranteed": streak % EGG_GUARANTEE_EVERY == 0}
