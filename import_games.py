"""Chess.com game importer — fetches new games and appends to master PGN."""

import json
import os
import requests

CHESS_COM_USER = "alexr456789"
DATA_DIR = os.path.dirname(os.path.abspath(__file__))
MASTER_PGN = os.path.join(DATA_DIR, "my_games.pgn")
STATE_FILE = os.path.join(DATA_DIR, ".import_state.json")


def load_state():
    if os.path.isfile(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"last_timestamp": 0}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def fetch_new_games(username=CHESS_COM_USER):
    """Fetch all games newer than last import, return PGN text and count."""
    state = load_state()
    last_ts = state["last_timestamp"]
    headers = {"User-Agent": "FischerChess/1.0 (local puzzle trainer)"}

    # Get archive list
    r = requests.get(f"https://api.chess.com/pub/player/{username}/games/archives", headers=headers)
    r.raise_for_status()
    archives = r.json().get("archives", [])

    new_games_pgn = []
    max_ts = last_ts

    for url in archives:
        r = requests.get(url, headers=headers)
        r.raise_for_status()
        games = r.json().get("games", [])
        for game in games:
            end_time = game.get("end_time", 0)
            if end_time <= last_ts:
                continue
            pgn = game.get("pgn", "")
            if pgn:
                new_games_pgn.append(pgn)
                max_ts = max(max_ts, end_time)

    if new_games_pgn:
        with open(MASTER_PGN, "a") as f:
            for pgn in new_games_pgn:
                f.write(pgn.strip() + "\n\n")
        state["last_timestamp"] = max_ts
        save_state(state)

    return len(new_games_pgn)


if __name__ == "__main__":
    count = fetch_new_games()
    print(f"Imported {count} new game(s) to {MASTER_PGN}")
