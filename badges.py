"""Badge system for Fischer Chess — Pokémon, Soccer, Premier League, Gems achievements."""

from datetime import date, timedelta

# Badge definitions: (tier, threshold, name, image_url)
# mystery_from: tiers >= this are hidden until earned
BADGE_CONFIG = {
    "first_try_streak": {
        "label": "First-Try Streak",
        "desc": "Solve puzzles correctly on the first attempt in a row",
        "mystery_from": 3,
        "tiers": [
            (1, 3, "Pikachu", "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/25.png"),
            (2, 7, "Raichu", "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/26.png"),
            (3, 15, "Zapdos", "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/145.png"),
            (4, 30, "Mewtwo", "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/150.png"),
        ],
    },
    "volume": {
        "label": "Volume",
        "desc": "Total puzzles solved (any method)",
        "mystery_from": 3,
        "tiers": [
            (1, 10, "Charmander", "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/4.png"),
            (2, 50, "Charmeleon", "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/5.png"),
            (3, 100, "Charizard", "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/6.png"),
            (4, 500, "Mew", "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/151.png"),
        ],
    },
    "daily_streak": {
        "label": "Daily Streak",
        "desc": "Solve at least 1 puzzle on consecutive days",
        "mystery_from": 3,
        "tiers": [
            (1, 3, "Messi", "/static/badges/messi.jpg"),
            (2, 7, "Ronaldo", "/static/badges/ronaldo.jpg"),
            (3, 30, "Zidane", "/static/badges/zidane.jpg"),
            (4, 100, "Pelé", "/static/badges/pele.jpg"),
        ],
    },
    "comeback_kid": {
        "label": "Comeback Kid",
        "desc": "Bookmark puzzles to 'Worth a 2nd Look' then solve them on retry",
        "mystery_from": 6,
        "tiers": [
            (1, 1, "Fulham", "/static/badges/fulham.svg"),
            (2, 3, "Brighton", "/static/badges/brighton.svg"),
            (3, 5, "Newcastle", "/static/badges/newcastle.svg"),
            (4, 7, "Aston Villa", "/static/badges/aston_villa.svg"),
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
            (1, 10, "Saka", "⚽"),
            (2, 25, "Palmer", "⚽"),
            (3, 50, "Salah", "⚽"),
            (4, 100, "Ødegaard", "⚽"),
            (5, 200, "De Bruyne", "⚽"),
            (6, 300, "Son", "⚽"),
            (7, 500, "Van Dijk", "⚽"),
            (8, 750, "Thierry Henry", "⚽"),
            (9, 1000, "Bergkamp", "⚽"),
            (10, 2000, "Shearer", "⚽"),
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
}

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
            newly_earned.append({"type": badge_type, "tier": tier, "name": name, "image": img})

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

    return {
        "volume": total_solved,
        "first_try_streak": first_try_streak,
        "daily_streak": daily_streak,
        "comeback_kid": comeback_count,
        "collector": total_games,
        "perfectionist": perfectionist_rate,
        "game_crusher": len(crushed),
    }
