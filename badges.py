"""Badge system for Fischer Chess — Pokémon, Soccer, Premier League, Gems, tactic and Pokédex achievements."""

from datetime import date, timedelta

# Badge definitions: (tier, threshold, name, image_url)
# mystery_from: tiers >= this are hidden until earned
BADGE_CONFIG = {
    "first_try_streak": {
        "label": "First-Try Streak",
        "desc": "Solve puzzles correctly on the first attempt in a row",
        "mystery_from": 3,
        "tiers": [
            (1, 3, "Pikachu", "/static/badges/pokemon_25.png"),
            (2, 7, "Raichu", "/static/badges/pokemon_26.png"),
            (3, 15, "Zapdos", "/static/badges/pokemon_145.png"),
            (4, 30, "Mewtwo", "/static/badges/pokemon_150.png"),
        ],
    },
    "volume": {
        "label": "Volume",
        "desc": "Total puzzles solved (any method)",
        "mystery_from": 3,
        "tiers": [
            (1, 10, "Charmander", "/static/badges/pokemon_4.png"),
            (2, 50, "Charmeleon", "/static/badges/pokemon_5.png"),
            (3, 100, "Charizard", "/static/badges/pokemon_6.png"),
            (4, 500, "Mew", "/static/badges/pokemon_151.png"),
        ],
    },
    "daily_streak": {
        "label": "Daily Streak",
        "desc": "Solve at least 1 puzzle on consecutive days",
        "mystery_from": 8,
        "tiers": [
            (1, 1, "Rice", "/static/badges/rice.jpg"),
            (2, 2, "Foden", "/static/badges/foden.jpg"),
            (3, 3, "Martinelli", "/static/badges/martinelli.jpg"),
            (4, 4, "Mount", "/static/badges/mount.jpg"),
            (5, 5, "Trent", "/static/badges/trent.jpg"),
            (6, 6, "Bellingham", "/static/badges/bellingham.jpg"),
            (7, 7, "Messi", "/static/badges/messi.jpg"),
            (8, 10, "Rashford", "/static/badges/rashford.jpg"),
            (9, 14, "Ronaldo", "/static/badges/ronaldo.jpg"),
            (10, 21, "Hazard", "/static/badges/hazard.jpg"),
            (11, 30, "Lampard", "/static/badges/lampard.jpg"),
            (12, 45, "Gerrard", "/static/badges/gerrard.jpg"),
            (13, 60, "Rooney", "/static/badges/rooney.jpg"),
            (14, 90, "Scholes", "/static/badges/scholes.jpg"),
            (15, 120, "Zidane", "/static/badges/zidane.jpg"),
            (16, 180, "Maradona", "/static/badges/maradona.jpg"),
            (17, 365, "Pelé", "/static/badges/pele.jpg"),
        ],
    },
    "comeback_kid": {
        "label": "Comeback Kid",
        "desc": "Bookmark puzzles to 'Worth a 2nd Look' then solve them on retry",
        "mystery_from": 6,
        "tiers": [
            (1, 1, "Fulham", "/static/badges/fulham.svg"),
            (2, 3, "Brighton", "/static/badges/brighton.png"),
            (3, 5, "Newcastle", "/static/badges/newcastle.svg"),
            (4, 7, "Aston Villa", "/static/badges/aston_villa.png"),
            (5, 10, "Tottenham", "/static/badges/tottenham.svg"),
            (6, 15, "Chelsea", "/static/badges/chelsea.svg"),
            (7, 20, "Liverpool", "/static/badges/liverpool.svg"),
            (8, 25, "Man City", "/static/badges/man_city.svg"),
            (9, 35, "Arsenal", "/static/badges/arsenal.svg"),
            (10, 50, "Real Madrid", "/static/badges/real_madrid.svg"),
        ],
    },
    "collector": {
        "label": "Collector",
        "desc": "Total games imported into your library",
        "mystery_from": 6,
        "tiers": [
            (1, 10, "Saka", "/static/badges/saka.jpg"),
            (2, 25, "Palmer", "/static/badges/palmer.jpg"),
            (3, 50, "Salah", "/static/badges/salah.jpg"),
            (4, 100, "Ødegaard", "/static/badges/odegaard.jpg"),
            (5, 200, "De Bruyne", "/static/badges/de_bruyne.jpg"),
            (6, 300, "Son", "/static/badges/son.jpg"),
            (7, 500, "Van Dijk", "/static/badges/van_dijk.jpg"),
            (8, 750, "Thierry Henry", "/static/badges/henry.jpg"),
            (9, 1000, "Bergkamp", "/static/badges/bergkamp.jpg"),
            (10, 2000, "Shearer", "/static/badges/shearer.jpg"),
        ],
    },
    "perfectionist": {
        "label": "Perfectionist",
        "desc": "Maintain high first-try solve rate over many puzzles",
        "mystery_from": 3,
        "tiers": [
            (1, 80, "Emerald", "💚"),
            (2, 85, "Sapphire", "💙"),
            (3, 90, "Ruby", "❤️"),
            (4, 95, "Diamond", "💎"),
        ],
    },
    "game_crusher": {
        "label": "Game Crusher",
        "desc": "Solve ALL puzzles from a single game on first try",
        "mystery_from": 4,
        "tiers": [
            (1, 1, "Ash", "/static/badges/ash.png"),
            (2, 3, "Misty", "/static/badges/misty.png"),
            (3, 5, "Brock", "/static/badges/brock.png"),
            (4, 10, "Gary Oak", "/static/badges/gary_oak.png"),
            (5, 20, "Red", "/static/badges/red.png"),
        ],
    },
    "pokedex": {
        "label": "Pokédex",
        "desc": "Catch different Pokémon by solving puzzles",
        "mystery_from": 5,
        "tiers": [
            (1, 10, "Poké Ball", "/static/badges/poke-ball.png"),
            (2, 30, "Great Ball", "/static/badges/great-ball.png"),
            (3, 60, "Ultra Ball", "/static/badges/ultra-ball.png"),
            (4, 100, "Master Ball", "/static/badges/master-ball.png"),
            (5, 151, "Pokémon Master", "🏆"),
        ],
    },
}


def _poke(n):
    return f"/static/pokedex/{n}.png"


# Tactic badges: solve puzzles of a tactic type to evolve a Pokémon line.
# badge_type -> (label, desc, tactic labels that count, [(threshold, name, dex number)])
TACTIC_BADGES = {
    "tactic_fork": ("Fork Master", "Solve fork puzzles", {"fork"},
                    [(3, "Abra", 63), (10, "Kadabra", 64), (25, "Alakazam", 65)]),
    "tactic_pin": ("Pin Master", "Solve pin puzzles", {"pin"},
                   [(3, "Caterpie", 10), (10, "Metapod", 11), (25, "Butterfree", 12)]),
    "tactic_skewer": ("Skewer Master", "Solve skewer puzzles", {"skewer"},
                      [(3, "Weedle", 13), (10, "Kakuna", 14), (25, "Beedrill", 15)]),
    "tactic_discovered": ("Sneak Attack", "Solve discovered attack puzzles",
                          {"discovered attack", "discovered check"},
                          [(3, "Gastly", 92), (10, "Haunter", 93), (25, "Gengar", 94)]),
    "tactic_mate": ("Checkmate Hunter", "Solve checkmate puzzles",
                    {"checkmate", "back rank mate", "smothered mate"},
                    [(3, "Dratini", 147), (10, "Dragonair", 148), (25, "Dragonite", 149)]),
    "tactic_check": ("Check Power", "Solve puzzles that start with a check", {"check"},
                     [(3, "Machop", 66), (10, "Machoke", 67), (25, "Machamp", 68)]),
    "tactic_capture": ("Capture Crew", "Solve capture puzzles", {"capture"},
                       [(3, "Bulbasaur", 1), (10, "Ivysaur", 2), (25, "Venusaur", 3)]),
    "tactic_trap": ("Piece Trapper", "Solve trapped-piece puzzles", {"trapped piece"},
                    [(3, "Squirtle", 7), (10, "Wartortle", 8), (25, "Blastoise", 9)]),
    "tactic_promotion": ("Promotion Power", "Solve pawn promotion puzzles", {"promotion"},
                         [(1, "Magikarp", 129), (5, "Gyarados", 130)]),
    "tactic_positional": ("Smart Mover", "Solve quiet positional puzzles", {"positional"},
                          [(3, "Pidgey", 16), (10, "Pidgeotto", 17), (25, "Pidgeot", 18)]),
}

for _type, (_label, _desc, _tags, _steps) in TACTIC_BADGES.items():
    BADGE_CONFIG[_type] = {
        "label": _label,
        "desc": _desc,
        "mystery_from": 3,
        "tiers": [(i + 1, t, name, _poke(n)) for i, (t, name, n) in enumerate(_steps)],
    }


def _tactic_counts(conn, user_id):
    """Count solved puzzles per tactic badge type (a puzzle can count toward several)."""
    counts = {k: 0 for k in TACTIC_BADGES}
    for (tactics,) in conn.execute(
            "SELECT tactics FROM puzzles WHERE user_id = ? AND status IN ('solved_first_try','solved_retry')",
            (user_id,)):
        tags = {t.strip() for t in (tactics or "").split(",") if t.strip()}
        for k, (_l, _d, wanted, _s) in TACTIC_BADGES.items():
            if tags & wanted:
                counts[k] += 1
    return counts

# Flat format for API compatibility
BADGES = {k: v["tiers"] for k, v in BADGE_CONFIG.items()}
BADGE_META = {k: {"label": v["label"], "desc": v["desc"], "mystery_from": v["mystery_from"]} for k, v in BADGE_CONFIG.items()}


def check_badges(conn, user_id):
    """Check all badge conditions and award any newly earned badges."""
    newly_earned = []
    existing = set()
    for r in conn.execute("SELECT badge_type, tier FROM badges WHERE user_id = ?", (user_id,)).fetchall():
        existing.add((r[0], r[1]))

    def award(badge_type, tier, name, img):
        if (badge_type, tier) not in existing:
            conn.execute("INSERT INTO badges (user_id, badge_type, tier, name, image_url) VALUES (?,?,?,?,?)",
                         (user_id, badge_type, tier, name, img))
            earned = {"type": badge_type, "tier": tier, "name": name, "image": img}
            # Previous tier lets the frontend play an evolution (e.g. Abra -> Kadabra).
            prev = [t for t in BADGES.get(badge_type, []) if t[0] == tier - 1]
            if prev:
                earned["prev_name"], earned["prev_image"] = prev[0][2], prev[0][3]
            newly_earned.append(earned)

    # --- Volume ---
    total_solved = conn.execute(
        "SELECT COUNT(*) FROM puzzles WHERE user_id = ? AND status IN ('solved_first_try', 'solved_retry')",
        (user_id,)).fetchone()[0]
    for tier, threshold, name, img in BADGES["volume"]:
        if total_solved >= threshold:
            award("volume", tier, name, img)

    # --- First-try streak ---
    rows = conn.execute(
        "SELECT status FROM puzzles WHERE user_id = ? AND status IN ('solved_first_try','solved_retry') ORDER BY solved_at DESC",
        (user_id,)).fetchall()
    streak = 0
    for r in rows:
        if r[0] == "solved_first_try":
            streak += 1
        else:
            break
    for tier, threshold, name, img in BADGES["first_try_streak"]:
        if streak >= threshold:
            award("first_try_streak", tier, name, img)

    # --- Daily streak ---
    day_rows = conn.execute(
        "SELECT DISTINCT date(solved_at) as d FROM puzzles WHERE user_id = ? AND solved_at IS NOT NULL ORDER BY d DESC",
        (user_id,)).fetchall()
    daily_streak = _calc_daily_streak(day_rows)
    for tier, threshold, name, img in BADGES["daily_streak"]:
        if daily_streak >= threshold:
            award("daily_streak", tier, name, img)

    # --- Comeback Kid: bookmarked puzzles solved on retry ---
    comeback_count = conn.execute(
        "SELECT COUNT(*) FROM puzzles WHERE user_id = ? AND status = 'solved_retry'",
        (user_id,)).fetchone()[0]
    for tier, threshold, name, img in BADGES["comeback_kid"]:
        if comeback_count >= threshold:
            award("comeback_kid", tier, name, img)

    # --- Collector: total games imported ---
    total_games = conn.execute(
        "SELECT COUNT(*) FROM games WHERE user_id = ?", (user_id,)).fetchone()[0]
    for tier, threshold, name, img in BADGES["collector"]:
        if total_games >= threshold:
            award("collector", tier, name, img)

    # --- Perfectionist: first-try rate >= threshold% with minimum solves ---
    min_solves = [20, 50, 100, 200]
    if total_solved > 0:
        first_try_count = conn.execute(
            "SELECT COUNT(*) FROM puzzles WHERE user_id = ? AND status = 'solved_first_try'",
            (user_id,)).fetchone()[0]
        rate = (first_try_count / total_solved) * 100 if total_solved else 0
        for i, (tier, threshold, name, img) in enumerate(BADGES["perfectionist"]):
            if rate >= threshold and total_solved >= min_solves[i]:
                award("perfectionist", tier, name, img)

    # --- Game Crusher: games where ALL puzzles solved first-try ---
    crushed = conn.execute("""
        SELECT game_id FROM puzzles WHERE user_id = ? AND game_id IS NOT NULL
        GROUP BY game_id
        HAVING COUNT(*) = SUM(CASE WHEN status = 'solved_first_try' THEN 1 ELSE 0 END)
        AND COUNT(*) > 0
    """, (user_id,)).fetchall()
    crushed_count = len(crushed)
    for tier, threshold, name, img in BADGES["game_crusher"]:
        if crushed_count >= threshold:
            award("game_crusher", tier, name, img)

    # --- Tactic evolution lines ---
    for badge_type, count in _tactic_counts(conn, user_id).items():
        for tier, threshold, name, img in BADGES[badge_type]:
            if count >= threshold:
                award(badge_type, tier, name, img)

    # --- Pokédex: unique Pokémon caught ---
    from pokedex import unique_caught
    caught = unique_caught(conn, user_id)
    for tier, threshold, name, img in BADGES["pokedex"]:
        if caught >= threshold:
            award("pokedex", tier, name, img)

    if newly_earned:
        conn.commit()
    return newly_earned


def _calc_daily_streak(day_rows):
    daily_streak = 0
    today = date.today()
    expected = today
    for r in day_rows:
        if r[0] is None:
            break
        d = date.fromisoformat(r[0])
        if d == expected:
            daily_streak += 1
            expected -= timedelta(days=1)
        elif daily_streak == 0 and d == today - timedelta(days=1):
            daily_streak = 1
            expected = d - timedelta(days=1)
        else:
            break
    return daily_streak


def get_user_badges(conn, user_id):
    """Get all earned badges for a user."""
    return conn.execute(
        "SELECT badge_type, tier, name, image_url, earned_at FROM badges WHERE user_id = ? ORDER BY earned_at DESC",
        (user_id,)).fetchall()


def get_progress(conn, user_id):
    """Get current progress toward next badges."""
    total_solved = conn.execute(
        "SELECT COUNT(*) FROM puzzles WHERE user_id = ? AND status IN ('solved_first_try', 'solved_retry')",
        (user_id,)).fetchone()[0]

    rows = conn.execute(
        "SELECT status FROM puzzles WHERE user_id = ? AND status IN ('solved_first_try','solved_retry') ORDER BY solved_at DESC",
        (user_id,)).fetchall()
    first_try_streak = 0
    for r in rows:
        if r[0] == "solved_first_try":
            first_try_streak += 1
        else:
            break

    day_rows = conn.execute(
        "SELECT DISTINCT date(solved_at) as d FROM puzzles WHERE user_id = ? AND solved_at IS NOT NULL ORDER BY d DESC",
        (user_id,)).fetchall()
    daily_streak = _calc_daily_streak(day_rows)

    comeback_count = conn.execute(
        "SELECT COUNT(*) FROM puzzles WHERE user_id = ? AND status = 'solved_retry'",
        (user_id,)).fetchone()[0]

    total_games = conn.execute(
        "SELECT COUNT(*) FROM games WHERE user_id = ?", (user_id,)).fetchone()[0]

    first_try_count = conn.execute(
        "SELECT COUNT(*) FROM puzzles WHERE user_id = ? AND status = 'solved_first_try'",
        (user_id,)).fetchone()[0]
    perfectionist_rate = round((first_try_count / total_solved) * 100, 1) if total_solved >= 20 else 0

    crushed = conn.execute("""
        SELECT game_id FROM puzzles WHERE user_id = ? AND game_id IS NOT NULL
        GROUP BY game_id
        HAVING COUNT(*) = SUM(CASE WHEN status = 'solved_first_try' THEN 1 ELSE 0 END)
        AND COUNT(*) > 0
    """, (user_id,)).fetchall()

    from pokedex import unique_caught

    return {
        **_tactic_counts(conn, user_id),
        "pokedex": unique_caught(conn, user_id),
        "volume": total_solved,
        "first_try_streak": first_try_streak,
        "daily_streak": daily_streak,
        "comeback_kid": comeback_count,
        "collector": total_games,
        "perfectionist": perfectionist_rate,
        "game_crusher": len(crushed),
    }
