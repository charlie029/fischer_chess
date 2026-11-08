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
    """Get puzzles for the main page queue: active first, then solved_retry, then bookmarked."""
    conn = get_db()
    try:
        return conn.execute("""
            SELECT p.*, g.date as game_date, g.white as game_white, g.black as game_black,
                   g.event as game_event, g.result as game_result
            FROM puzzles p LEFT JOIN games g ON p.game_id = g.id
            WHERE p.user_id = ? AND p.status IN ('active', 'solved_retry', 'bookmarked')
            ORDER BY CASE p.status WHEN 'active' THEN 0 WHEN 'solved_retry' THEN 1 WHEN 'bookmarked' THEN 2 END, p.created_at
        """, (user_id,)).fetchall()
    finally:
        conn.close()


def update_puzzle_status(puzzle_id, status):
    from badges import check_badges
    conn = get_db()
    try:
        if status in ("solved_first_try", "solved_retry"):
            conn.execute("UPDATE puzzles SET status = ?, solved_at = CURRENT_TIMESTAMP WHERE id = ?",
                         (status, puzzle_id))
        else:
            conn.execute("UPDATE puzzles SET status = ? WHERE id = ?", (status, puzzle_id))
        conn.commit()
        # Check badges after a solve
        if status in ("solved_first_try", "solved_retry"):
            row = conn.execute("SELECT user_id FROM puzzles WHERE id = ?", (puzzle_id,)).fetchone()
            if row:
                newly_earned = check_badges(conn, row[0])
                return newly_earned
        return []
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
