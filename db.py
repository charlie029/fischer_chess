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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (game_id) REFERENCES games(id)
        );

        CREATE INDEX IF NOT EXISTS idx_games_user ON games(user_id);
        CREATE INDEX IF NOT EXISTS idx_games_date ON games(date);
        CREATE INDEX IF NOT EXISTS idx_puzzles_user ON puzzles(user_id);
        CREATE INDEX IF NOT EXISTS idx_puzzles_game ON puzzles(game_id);
    """)
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
        conn.execute("""INSERT INTO puzzles 
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
        q = "SELECT * FROM puzzles WHERE user_id = ? ORDER BY created_at DESC"
        if limit:
            q += f" LIMIT {int(limit)}"
        return conn.execute(q, (user_id,)).fetchall()
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


# Initialize on import
init_db()
