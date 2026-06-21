"""Badge system for Fischer Chess — Pokémon + Soccer player achievements."""

# Badge definitions: (type, tier, threshold, name, image_url)
BADGES = {
    "first_try_streak": [
        (1, 3, "Pikachu", "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/25.png"),
        (2, 7, "Raichu", "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/26.png"),
        (3, 15, "Zapdos", "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/145.png"),
        (4, 30, "Mewtwo", "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/150.png"),
    ],
    "volume": [
        (1, 10, "Charmander", "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/4.png"),
        (2, 50, "Charmeleon", "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/5.png"),
        (3, 100, "Charizard", "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/6.png"),
        (4, 500, "Mew", "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/151.png"),
    ],
    "daily_streak": [
        (1, 3, "Messi", "https://img.a.transfermarkt.technology/portrait/small/28003-1710080339.jpg"),
        (2, 7, "Ronaldo", "https://img.a.transfermarkt.technology/portrait/small/8198-1714035801.jpg"),
        (3, 30, "Zidane", "https://img.a.transfermarkt.technology/portrait/small/3111-1686927741.jpg"),
        (4, 100, "Pelé", "https://img.a.transfermarkt.technology/portrait/small/5765-1672928070.jpg"),
    ],
}


def check_badges(conn, user_id):
    """Check all badge conditions and award any newly earned badges. Returns list of newly earned."""
    newly_earned = []

    # Get current badges
    existing = set()
    for r in conn.execute("SELECT badge_type, tier FROM badges WHERE user_id = ?", (user_id,)).fetchall():
        existing.add((r[0], r[1]))

    # --- Volume: total puzzles solved (first_try + retry) ---
    total_solved = conn.execute(
        "SELECT COUNT(*) FROM puzzles WHERE user_id = ? AND status IN ('solved_first_try', 'solved_retry')",
        (user_id,)
    ).fetchone()[0]

    for tier, threshold, name, img in BADGES["volume"]:
        if ("volume", tier) not in existing and total_solved >= threshold:
            conn.execute("INSERT INTO badges (user_id, badge_type, tier, name, image_url) VALUES (?,?,?,?,?)",
                         (user_id, "volume", tier, name, img))
            newly_earned.append({"type": "volume", "tier": tier, "name": name, "image": img})

    # --- First-try streak: current consecutive first-try solves ---
    rows = conn.execute(
        "SELECT status FROM puzzles WHERE user_id = ? AND status IN ('solved_first_try','solved_retry') ORDER BY solved_at DESC",
        (user_id,)
    ).fetchall()
    streak = 0
    for r in rows:
        if r[0] == "solved_first_try":
            streak += 1
        else:
            break

    for tier, threshold, name, img in BADGES["first_try_streak"]:
        if ("first_try_streak", tier) not in existing and streak >= threshold:
            conn.execute("INSERT INTO badges (user_id, badge_type, tier, name, image_url) VALUES (?,?,?,?,?)",
                         (user_id, "first_try_streak", tier, name, img))
            newly_earned.append({"type": "first_try_streak", "tier": tier, "name": name, "image": img})

    # --- Daily streak: consecutive days with at least 1 solve ---
    day_rows = conn.execute(
        "SELECT DISTINCT date(solved_at) as d FROM puzzles WHERE user_id = ? AND solved_at IS NOT NULL ORDER BY d DESC",
        (user_id,)
    ).fetchall()
    daily_streak = 0
    from datetime import date, timedelta
    today = date.today()
    expected = today
    for r in day_rows:
        if r[0] is None:
            break
        d = date.fromisoformat(r[0])
        if d == expected:
            daily_streak += 1
            expected -= timedelta(days=1)
        elif d == expected - timedelta(days=1):
            # Allow checking from yesterday if no solve today yet
            if daily_streak == 0:
                daily_streak = 1
                expected = d - timedelta(days=1)
            else:
                break
        else:
            break

    for tier, threshold, name, img in BADGES["daily_streak"]:
        if ("daily_streak", tier) not in existing and daily_streak >= threshold:
            conn.execute("INSERT INTO badges (user_id, badge_type, tier, name, image_url) VALUES (?,?,?,?,?)",
                         (user_id, "daily_streak", tier, name, img))
            newly_earned.append({"type": "daily_streak", "tier": tier, "name": name, "image": img})

    if newly_earned:
        conn.commit()
    return newly_earned


def get_user_badges(conn, user_id):
    """Get all earned badges for a user."""
    return conn.execute(
        "SELECT badge_type, tier, name, image_url, earned_at FROM badges WHERE user_id = ? ORDER BY earned_at DESC",
        (user_id,)
    ).fetchall()
