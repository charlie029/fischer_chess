"""Database module for Fischer Chess — SQLite storage for users, games, and puzzles."""

import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fischer.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            chess_com_username TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            pgn TEXT NOT NULL,
            white TEXT,
            black TEXT,
            result TEXT,
            date TEXT,
            event TEXT,
            total_moves INTEGER,
            chess_com_id TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS puzzles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            game_id INTEGER,
            fen TEXT NOT NULL,
            best_move_uci TEXT,
            best_move_san TEXT,
            played_move TEXT,
            reason TEXT,
            drop_cp INTEGER,
            move_number INTEGER,
            turn TEXT,
            tactics TEXT,
            acceptable_uci TEXT,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (game_id) REFERENCES games(id)
        );

        CREATE INDEX IF NOT EXISTS idx_games_user ON games(user_id);
        CREATE INDEX IF NOT EXISTS idx_games_date ON games(date);
        CREATE INDEX IF NOT EXISTS idx_puzzles_user ON puzzles(user_id);
        CREATE INDEX IF NOT EXISTS idx_puzzles_game ON puzzles(game_id);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_games_dedup ON games(user_id, white, black, date, total_moves);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_puzzles_dedup ON puzzles(user_id, game_id, fen, best_move_uci);
    """)
    # Migration: add status column if missing
    cols = [r[1] for r in conn.execute("PRAGMA table_info(puzzles)").fetchall()]
    if "status" not in cols:
        conn.execute("ALTER TABLE puzzles ADD COLUMN status TEXT DEFAULT 'active'")
    if "solved_at" not in cols:
        conn.execute("ALTER TABLE puzzles ADD COLUMN solved_at TIMESTAMP")
    # 1 once a solved_retry puzzle has had its one comeback; it then leaves the queue.
    if "retry_done" not in cols:
        conn.execute("ALTER TABLE puzzles ADD COLUMN retry_done INTEGER NOT NULL DEFAULT 0")

    # Badges table
    conn.execute("""CREATE TABLE IF NOT EXISTS badges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        badge_type TEXT NOT NULL,
        tier INTEGER NOT NULL,
        name TEXT,
        image_url TEXT,
        earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id),
        UNIQUE(user_id, badge_type, tier)
    )""")

    # Pokédex catches: one Pokémon per solved puzzle. puzzle_id has no FK on purpose, so
    # deleting a game or puzzle never takes away a Pokémon the kid already caught.
    conn.execute("""CREATE TABLE IF NOT EXISTS pokedex_catches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        pokemon_id INTEGER NOT NULL,
        puzzle_id INTEGER,
        caught_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id),
        UNIQUE(user_id, puzzle_id)
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pokedex_user ON pokedex_catches(user_id)")

    # Daily egg: one per user per local day (YYYY-MM-DD), hatched by the day's first solve.
    conn.execute("""CREATE TABLE IF NOT EXISTS daily_eggs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        day TEXT NOT NULL,
        pokemon_id INTEGER NOT NULL,
        hatched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id),
        UNIQUE(user_id, day)
    )""")

    # Think-time log: one row per move tried on an unsolved puzzle. think_ms is the visible-tab
    # time since the puzzle loaded (attempt 1) or since the previous wrong try (later attempts).
    conn.execute("""CREATE TABLE IF NOT EXISTS puzzle_attempts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        puzzle_id INTEGER,
        attempt_no INTEGER NOT NULL,
        think_ms INTEGER NOT NULL,
        correct INTEGER NOT NULL,
        hinted INTEGER NOT NULL DEFAULT 0,
        deep_think INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_attempts_user ON puzzle_attempts(user_id)")
    # Kotov candidate moves: comma-separated UCI the player listed before moving (NULL = none),
    # whether a winning move (best or acceptable) was on that list, and the Kotov bonus.
    att_cols = [r[1] for r in conn.execute("PRAGMA table_info(puzzle_attempts)").fetchall()]
    if "candidates" not in att_cols:
        conn.execute("ALTER TABLE puzzle_attempts ADD COLUMN candidates TEXT")
    if "good_listed" not in att_cols:
        conn.execute("ALTER TABLE puzzle_attempts ADD COLUMN good_listed INTEGER")
    if "kotov" not in att_cols:
        conn.execute("ALTER TABLE puzzle_attempts ADD COLUMN kotov INTEGER NOT NULL DEFAULT 0")

    # Migration: add lichess_username to users table
    user_cols = [r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
    if "lichess_username" not in user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN lichess_username TEXT")

    # Migration: add lichess_id to games table
    game_cols = [r[1] for r in conn.execute("PRAGMA table_info(games)").fetchall()]
    if "lichess_id" not in game_cols:
        conn.execute("ALTER TABLE games ADD COLUMN lichess_id TEXT")

    # Game analyses table for loss classification
    conn.execute("""CREATE TABLE IF NOT EXISTS game_analyses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        game_id INTEGER NOT NULL,
        result TEXT,
        user_color TEXT,
        loss_category TEXT,
        loss_description TEXT,
        worst_move_number INTEGER,
        worst_move_san TEXT,
        worst_move_cp_loss INTEGER,
        eval_before_worst REAL,
        eval_after_worst REAL,
        total_blunders INTEGER DEFAULT 0,
        total_mistakes INTEGER DEFAULT 0,
        total_inaccuracies INTEGER DEFAULT 0,
        avg_cp_loss REAL,
        accuracy REAL,
        opening_name TEXT,
        time_control TEXT,
        analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (game_id) REFERENCES games(id),
        UNIQUE(game_id)
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_analysis_user ON game_analyses(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_analysis_category ON game_analyses(loss_category)")

    conn.commit()
    conn.close()


# --- User operations ---

def create_user(username, chess_com_username=None):
    conn = get_db()
    try:
        conn.execute("INSERT INTO users (username, chess_com_username) VALUES (?, ?)",
                     (username, chess_com_username))
        conn.commit()
        return conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    finally:
        conn.close()


def get_user(username):
    conn = get_db()
    try:
        return conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    finally:
        conn.close()


def list_users():
    conn = get_db()
    try:
        return conn.execute("SELECT * FROM users ORDER BY username").fetchall()
    finally:
        conn.close()


def delete_user(username):
    conn = get_db()
    try:
        user = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if not user:
            return False
        conn.execute("DELETE FROM puzzles WHERE user_id = ?", (user["id"],))
        conn.execute("DELETE FROM games WHERE user_id = ?", (user["id"],))
        conn.execute("DELETE FROM badges WHERE user_id = ?", (user["id"],))
        conn.execute("DELETE FROM pokedex_catches WHERE user_id = ?", (user["id"],))
        conn.execute("DELETE FROM daily_eggs WHERE user_id = ?", (user["id"],))
        conn.execute("DELETE FROM puzzle_attempts WHERE user_id = ?", (user["id"],))
        conn.execute("DELETE FROM users WHERE id = ?", (user["id"],))
        conn.commit()
        return True
    finally:
        conn.close()


# --- Game operations ---

def save_game(user_id, pgn, white, black, result, date, event, total_moves, chess_com_id=None):
    conn = get_db()
    try:
        conn.execute("""INSERT OR IGNORE INTO games 
                        (user_id, pgn, white, black, result, date, event, total_moves, chess_com_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                     (user_id, pgn, white, black, result, date, event, total_moves, chess_com_id))
        conn.commit()
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    finally:
        conn.close()


def get_user_games(user_id, limit=None):
    conn = get_db()
    try:
        q = "SELECT * FROM games WHERE user_id = ? ORDER BY date DESC"
        if limit:
            q += f" LIMIT {int(limit)}"
        return conn.execute(q, (user_id,)).fetchall()
    finally:
        conn.close()


def find_game_id(user_id, white, black, date, total_moves):
    """Return the id of an existing game matching the dedup key (idx_games_dedup), or None."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id FROM games WHERE user_id = ? AND white = ? AND black = ? AND date = ? AND total_moves = ?",
            (user_id, white, black, date, total_moves)).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def get_games_by_ids(user_id, game_ids):
    """Fetch specific games owned by user_id (used to analyze only newly imported games)."""
    ids = [int(i) for i in game_ids]
    if not ids:
        return []
    conn = get_db()
    try:
        placeholders = ",".join("?" * len(ids))
        q = f"SELECT * FROM games WHERE user_id = ? AND id IN ({placeholders}) ORDER BY date DESC"
        return conn.execute(q, (user_id, *ids)).fetchall()
    finally:
        conn.close()


def delete_game(game_id):
    conn = get_db()
    try:
        conn.execute("DELETE FROM puzzles WHERE game_id = ?", (game_id,))
        conn.execute("DELETE FROM games WHERE id = ?", (game_id,))
        conn.commit()
        return True
    finally:
        conn.close()


# --- Puzzle operations ---

def save_puzzle(user_id, game_id, fen, best_move_uci, best_move_san, played_move,
                reason, drop_cp, move_number, turn, tactics, acceptable_uci):
    conn = get_db()
    try:
        conn.execute("""INSERT OR IGNORE INTO puzzles 
                        (user_id, game_id, fen, best_move_uci, best_move_san, played_move,
                         reason, drop_cp, move_number, turn, tactics, acceptable_uci)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                     (user_id, game_id, fen, best_move_uci, best_move_san, played_move,
                      reason, drop_cp, move_number, turn, tactics, acceptable_uci))
        conn.commit()
    finally:
        conn.close()


def get_user_puzzles(user_id, limit=None):
    conn = get_db()
    try:
        q = """SELECT p.*, g.date as game_date, g.white as game_white, g.black as game_black,
               CASE WHEN g.chess_com_id IS NOT NULL THEN 'Chess.com' ELSE 'Local PGN' END as source
               FROM puzzles p LEFT JOIN games g ON p.game_id = g.id
               WHERE p.user_id = ? ORDER BY p.created_at DESC"""
        if limit:
            q += f" LIMIT {int(limit)}"
        return conn.execute(q, (user_id,)).fetchall()
    finally:
        conn.close()


def get_queue_puzzles(user_id):
    """Get puzzles for the main page queue: active, then bookmarked, then solved_retry at the bottom.

    A puzzle solved only after a wrong try comes back once; once that comeback is solved
    (retry_done = 1) it leaves the queue. A first-try solve archives it as usual.
    """
    conn = get_db()
    try:
        return conn.execute("""
            SELECT p.*, g.date as game_date, g.white as game_white, g.black as game_black,
                   g.event as game_event, g.result as game_result
            FROM puzzles p LEFT JOIN games g ON p.game_id = g.id
            WHERE p.user_id = ? AND (p.status IN ('active', 'bookmarked')
                                     OR (p.status = 'solved_retry' AND p.retry_done = 0))
            ORDER BY CASE p.status WHEN 'active' THEN 0 WHEN 'bookmarked' THEN 1 WHEN 'solved_retry' THEN 2 END,
                     CASE WHEN p.status = 'solved_retry' THEN p.solved_at END, p.created_at
        """, (user_id,)).fetchall()
    finally:
        conn.close()


DEEP_THINK_SECS = 10          # first-try solve after at least this long earns the bonus
MAX_THINK_MS = 10 * 60 * 1000  # cap so a board left open overnight doesn't skew stats


KOTOV_MIN_CANDIDATES = 2      # list at least this many moves, then play one of them
_NO_BONUS = {"deep_think": False, "kotov": False}


def _same_move(a, b):
    # Drag-and-drop always promotes to a queen, so compare from/to squares only.
    return bool(a) and bool(b) and a[:4] == b[:4]


def _insert_attempt(conn, puzzle_id, attempt):
    """Log one move attempt and work out its bonuses. Caller commits.

    attempt from the client: {"attempt_no", "think_ms", "correct", "hinted",
    "candidates": [uci, ...], "played": uci}.
    Returns {"deep_think": bool, "kotov": bool}.
    """
    row = conn.execute("SELECT user_id, best_move_uci, acceptable_uci FROM puzzles WHERE id = ?",
                       (puzzle_id,)).fetchone()
    if not row:
        return dict(_NO_BONUS)
    try:
        think_ms = max(0, min(int(attempt.get("think_ms") or 0), MAX_THINK_MS))
        attempt_no = max(1, int(attempt.get("attempt_no") or 1))
    except (TypeError, ValueError):
        return dict(_NO_BONUS)
    correct = bool(attempt.get("correct"))
    hinted = bool(attempt.get("hinted"))
    clean_first_try = correct and attempt_no == 1 and not hinted
    deep = clean_first_try and think_ms >= DEEP_THINK_SECS * 1000

    raw = attempt.get("candidates")
    cands = [c for c in raw if isinstance(c, str) and 4 <= len(c) <= 5][:10] if isinstance(raw, list) else []
    played = attempt.get("played") if isinstance(attempt.get("played"), str) else ""
    winning = [row["best_move_uci"]] + [a for a in (row["acceptable_uci"] or "").split(",") if a]
    good_listed = any(_same_move(c, w) for c in cands for w in winning) if cands else None
    kotov = (clean_first_try and len(cands) >= KOTOV_MIN_CANDIDATES
             and any(_same_move(c, played) for c in cands))

    conn.execute("""INSERT INTO puzzle_attempts
                    (user_id, puzzle_id, attempt_no, think_ms, correct, hinted, deep_think,
                     candidates, good_listed, kotov)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                 (row["user_id"], puzzle_id, attempt_no, think_ms, int(correct), int(hinted),
                  int(deep), ",".join(cands) or None,
                  None if good_listed is None else int(good_listed), int(kotov)))
    return {"deep_think": deep, "kotov": kotov}


def record_attempt(puzzle_id, attempt):
    """Log an attempt that doesn't change puzzle status (wrong move, or re-solving a bookmark)."""
    conn = get_db()
    try:
        bonus = _insert_attempt(conn, puzzle_id, attempt)
        conn.commit()
        return bonus
    finally:
        conn.close()


def get_kotov_stats(user_id):
    """Split first-try misses into "didn't see it" (vision) vs "saw it, picked another" (judgment)."""
    conn = get_db()
    try:
        rows = conn.execute("""SELECT correct, good_listed FROM puzzle_attempts
                               WHERE user_id = ? AND attempt_no = 1 AND good_listed IS NOT NULL""",
                            (user_id,)).fetchall()
        bonuses = conn.execute("SELECT COUNT(*) FROM puzzle_attempts WHERE user_id = ? AND kotov = 1",
                               (user_id,)).fetchone()[0]
    finally:
        conn.close()
    listed = [r for r in rows if r["good_listed"]]
    pct = lambda n, d: round(100 * n / d) if d else None
    return {
        "puzzles": len(rows),
        "kotov_bonuses": bonuses,
        "min_candidates": KOTOV_MIN_CANDIDATES,
        "found_rate": pct(len(listed), len(rows)),          # a winning move made the list
        "picked_rate": pct(sum(r["correct"] for r in listed), len(listed)),  # ...and got played
        "missed_unseen": sum(1 for r in rows if not r["good_listed"] and not r["correct"]),
        "missed_seen": sum(1 for r in listed if not r["correct"]),
    }


def get_think_stats(user_id):
    """First-attempt accuracy by think-time bucket, so a kid can see that slowing down pays."""
    buckets = [("Under 5s", 0, 5000), ("5-10s", 5000, 10000),
               ("10-30s", 10000, 30000), ("30s+", 30000, None)]
    conn = get_db()
    try:
        rows = conn.execute("""SELECT think_ms, correct FROM puzzle_attempts
                               WHERE user_id = ? AND attempt_no = 1 AND hinted = 0""",
                            (user_id,)).fetchall()
        deep = conn.execute("SELECT COUNT(*) FROM puzzle_attempts WHERE user_id = ? AND deep_think = 1",
                            (user_id,)).fetchone()[0]
    finally:
        conn.close()
    out = []
    for label, lo, hi in buckets:
        hits = [r["correct"] for r in rows if r["think_ms"] >= lo and (hi is None or r["think_ms"] < hi)]
        out.append({"label": label, "attempts": len(hits),
                    "accuracy": round(100 * sum(hits) / len(hits)) if hits else None})
    times = sorted(r["think_ms"] for r in rows)
    median = times[len(times) // 2] / 1000 if times else None
    return {"buckets": out, "median_secs": round(median, 1) if median is not None else None,
            "first_attempts": len(rows), "deep_thinks": deep, "deep_think_secs": DEEP_THINK_SECS}


def update_puzzle_status(puzzle_id, status, attempt=None):
    """Update a puzzle's status. On a solve, catch a Pokémon and check badges.

    attempt: optional think-time / candidate info for the solving move. Process is rewarded
    more than time: a Kotov solve moves the Pokémon roll one rarity row up, while a deep-think
    solve only makes a not-yet-caught Pokémon more likely.

    Returns {"new_badges": [...], "caught": {...} or None, "egg": {...} or None,
    "deep_think": bool, "kotov": bool}. The day's first solve also hatches the daily egg.
    """
    from badges import check_badges
    from pokedex import catch_for_puzzle, hatch_daily_egg
    conn = get_db()
    try:
        if status in ("solved_first_try", "solved_retry"):
            # A retry solve of a puzzle that was already solved_retry is its one comeback: done.
            prev = conn.execute("SELECT status FROM puzzles WHERE id = ?", (puzzle_id,)).fetchone()
            retry_done = int(status == "solved_retry" and prev is not None and prev[0] == "solved_retry")
            conn.execute("UPDATE puzzles SET status = ?, solved_at = CURRENT_TIMESTAMP, retry_done = ? "
                         "WHERE id = ?", (status, retry_done, puzzle_id))
        else:
            conn.execute("UPDATE puzzles SET status = ? WHERE id = ?", (status, puzzle_id))
        bonus = _insert_attempt(conn, puzzle_id, attempt) if attempt else dict(_NO_BONUS)
        conn.commit()
        result = {"new_badges": [], "caught": None, "egg": None, **bonus}
        if status in ("solved_first_try", "solved_retry"):
            row = conn.execute("SELECT user_id FROM puzzles WHERE id = ?", (puzzle_id,)).fetchone()
            if row:
                # Catch first so a new Pokédex milestone badge is awarded on this same solve.
                result["caught"] = catch_for_puzzle(conn, row[0], puzzle_id,
                                                    status == "solved_first_try",
                                                    bonus=int(bonus["kotov"]),
                                                    deep_think=bonus["deep_think"])
                result["egg"] = hatch_daily_egg(conn, row[0])
                conn.commit()
                result["new_badges"] = check_badges(conn, row[0])
        return result
    finally:
        conn.close()


# --- Stats queries ---

def get_user_stats(user_id):
    conn = get_db()
    try:
        row = conn.execute("""
            SELECT COUNT(*) as total_puzzles,
                   AVG(drop_cp) as avg_drop,
                   COUNT(DISTINCT game_id) as games_with_blunders
            FROM puzzles WHERE user_id = ?
        """, (user_id,)).fetchone()

        tactics_rows = conn.execute("""
            SELECT tactics, COUNT(*) as cnt FROM puzzles 
            WHERE user_id = ? AND tactics IS NOT NULL
            GROUP BY tactics ORDER BY cnt DESC
        """, (user_id,)).fetchall()

        # Flatten comma-separated tactics
        tactic_counts = {}
        for r in tactics_rows:
            for t in (r["tactics"] or "").split(","):
                t = t.strip()
                if t:
                    tactic_counts[t] = tactic_counts.get(t, 0) + r["cnt"]

        return {
            "total_puzzles": row["total_puzzles"],
            "avg_drop": round(row["avg_drop"] or 0),
            "games_with_blunders": row["games_with_blunders"],
            "tactic_breakdown": dict(sorted(tactic_counts.items(), key=lambda x: -x[1])),
        }
    finally:
        conn.close()


def get_user_trends(user_id):
    """Blunder rate per game over time. Only includes analyzed games (those with puzzles)."""
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT g.date, g.white, g.black, g.total_moves,
                   COUNT(p.id) as blunders, AVG(p.drop_cp) as avg_cp_loss
            FROM games g
            INNER JOIN puzzles p ON p.game_id = g.id
            WHERE g.user_id = ?
            GROUP BY g.id
            ORDER BY g.date
        """, (user_id,)).fetchall()

        return [{
            "date": r["date"],
            "game": f"{r['white']} vs {r['black']}",
            "blunders": r["blunders"],
            "total_moves": r["total_moves"] or 0,
            "blunder_rate": round(r["blunders"] / r["total_moves"], 4) if r["total_moves"] else 0,
            "avg_cp_loss": round(r["avg_cp_loss"] or 0),
        } for r in rows]
    finally:
        conn.close()


# --- Loss analysis operations ---

def update_user_lichess(username, lichess_username):
    """Update a user's Lichess username."""
    conn = get_db()
    try:
        conn.execute("UPDATE users SET lichess_username = ? WHERE username = ?",
                     (lichess_username, username))
        conn.commit()
    finally:
        conn.close()


def save_game_with_lichess_id(user_id, pgn, white, black, result, date, event,
                               total_moves, lichess_id):
    """Save a game imported from Lichess with dedup on lichess_id."""
    conn = get_db()
    try:
        # Check for existing by lichess_id first
        if lichess_id:
            existing = conn.execute(
                "SELECT id FROM games WHERE lichess_id = ?", (lichess_id,)
            ).fetchone()
            if existing:
                return None  # already imported

        conn.execute(
            """INSERT OR IGNORE INTO games
               (user_id, pgn, white, black, result, date, event, total_moves, lichess_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, pgn, white, black, result, date, event, total_moves, lichess_id)
        )
        conn.commit()
        row = conn.execute("SELECT last_insert_rowid()").fetchone()
        return row[0] if row[0] != 0 else None
    finally:
        conn.close()


def save_game_analysis(user_id, game_id, result, user_color, loss_category,
                       loss_description, worst_move_number, worst_move_san,
                       worst_move_cp_loss, eval_before_worst, eval_after_worst,
                       total_blunders, total_mistakes, total_inaccuracies,
                       avg_cp_loss, accuracy, opening_name, time_control):
    """Save or update a game's loss analysis."""
    conn = get_db()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO game_analyses
               (user_id, game_id, result, user_color, loss_category, loss_description,
                worst_move_number, worst_move_san, worst_move_cp_loss,
                eval_before_worst, eval_after_worst,
                total_blunders, total_mistakes, total_inaccuracies,
                avg_cp_loss, accuracy, opening_name, time_control)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, game_id, result, user_color, loss_category, loss_description,
             worst_move_number, worst_move_san, worst_move_cp_loss,
             eval_before_worst, eval_after_worst,
             total_blunders, total_mistakes, total_inaccuracies,
             avg_cp_loss, accuracy, opening_name, time_control)
        )
        conn.commit()
    finally:
        conn.close()


def get_unanalyzed_games(user_id, from_date=None, to_date=None):
    """Get games that don't have a loss analysis yet."""
    conn = get_db()
    try:
        q = """SELECT g.* FROM games g
               LEFT JOIN game_analyses ga ON ga.game_id = g.id
               WHERE g.user_id = ? AND ga.id IS NULL"""
        params = [user_id]
        if from_date:
            q += " AND g.date >= ?"
            params.append(from_date)
        if to_date:
            q += " AND g.date <= ?"
            params.append(to_date)
        q += " ORDER BY g.date"
        return conn.execute(q, params).fetchall()
    finally:
        conn.close()


def get_loss_summary(user_id, from_date=None, to_date=None):
    """Get aggregated loss analysis summary for a user."""
    conn = get_db()
    try:
        # Build date filter
        date_filter = ""
        params = [user_id]
        if from_date:
            date_filter += " AND g.date >= ?"
            params.append(from_date)
        if to_date:
            date_filter += " AND g.date <= ?"
            params.append(to_date)

        # Total games by result
        totals = conn.execute(f"""
            SELECT ga.result, COUNT(*) as cnt
            FROM game_analyses ga
            JOIN games g ON ga.game_id = g.id
            WHERE ga.user_id = ?{date_filter}
            GROUP BY ga.result
        """, params).fetchall()
        result_counts = {r["result"]: r["cnt"] for r in totals}

        # Loss category distribution
        cat_rows = conn.execute(f"""
            SELECT ga.loss_category, COUNT(*) as cnt
            FROM game_analyses ga
            JOIN games g ON ga.game_id = g.id
            WHERE ga.user_id = ? AND ga.result = 'loss'{date_filter}
            GROUP BY ga.loss_category
        """, params).fetchall()
        category_distribution = {r["loss_category"]: r["cnt"] for r in cat_rows}

        # Loss categories over time (by month)
        time_rows = conn.execute(f"""
            SELECT substr(g.date, 1, 7) as month, ga.loss_category, COUNT(*) as cnt
            FROM game_analyses ga
            JOIN games g ON ga.game_id = g.id
            WHERE ga.user_id = ? AND ga.result = 'loss'{date_filter}
            GROUP BY month, ga.loss_category
            ORDER BY month
        """, params).fetchall()

        # Pivot into {month: {category: count}}
        loss_over_time = {}
        for r in time_rows:
            m = r["month"]
            if m not in loss_over_time:
                loss_over_time[m] = {"month": m}
            loss_over_time[m][r["loss_category"]] = r["cnt"]
        loss_over_time_list = sorted(loss_over_time.values(), key=lambda x: x["month"])

        # Worst blunders (top 10)
        worst_rows = conn.execute(f"""
            SELECT ga.*, g.date, g.white, g.black, g.id as gid
            FROM game_analyses ga
            JOIN games g ON ga.game_id = g.id
            WHERE ga.user_id = ? AND ga.worst_move_cp_loss > 0{date_filter}
            ORDER BY ga.worst_move_cp_loss DESC
            LIMIT 10
        """, params).fetchall()
        worst_blunders = [{
            "game_id": r["gid"],
            "date": r["date"],
            "white": r["white"],
            "black": r["black"],
            "move_number": r["worst_move_number"],
            "move_san": r["worst_move_san"],
            "cp_loss": r["worst_move_cp_loss"],
            "eval_before": r["eval_before_worst"],
            "eval_after": r["eval_after_worst"],
            "loss_category": r["loss_category"],
        } for r in worst_rows]

        # Accuracy trend
        acc_rows = conn.execute(f"""
            SELECT g.date, ga.accuracy
            FROM game_analyses ga
            JOIN games g ON ga.game_id = g.id
            WHERE ga.user_id = ? AND ga.accuracy IS NOT NULL{date_filter}
            ORDER BY g.date
        """, params).fetchall()
        accuracy_trend = [{"date": r["date"], "accuracy": r["accuracy"]} for r in acc_rows]

        # Opening loss patterns
        opening_rows = conn.execute(f"""
            SELECT ga.opening_name,
                   COUNT(*) as total_losses,
                   ga.loss_category as top_category,
                   ROUND(AVG(ga.accuracy), 1) as avg_accuracy
            FROM game_analyses ga
            JOIN games g ON ga.game_id = g.id
            WHERE ga.user_id = ? AND ga.result = 'loss'
                  AND ga.opening_name != ''{date_filter}
            GROUP BY ga.opening_name
            ORDER BY total_losses DESC
            LIMIT 20
        """, params).fetchall()
        opening_losses = [{
            "opening_name": r["opening_name"],
            "total_losses": r["total_losses"],
            "top_category": r["top_category"],
            "avg_accuracy": r["avg_accuracy"],
        } for r in opening_rows]

        return {
            "total_games": sum(result_counts.values()),
            "wins": result_counts.get("win", 0),
            "losses": result_counts.get("loss", 0),
            "draws": result_counts.get("draw", 0),
            "loss_category_distribution": category_distribution,
            "loss_over_time": loss_over_time_list,
            "worst_blunders": worst_blunders,
            "accuracy_trend": accuracy_trend,
            "opening_losses": opening_losses,
        }
    finally:
        conn.close()


def get_loss_detail(game_id):
    """Get full loss analysis for a single game."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM game_analyses WHERE game_id = ?", (game_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# Initialize on import
init_db()
