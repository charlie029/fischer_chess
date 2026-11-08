"""Lichess game import module — fetch games from Lichess API via NDJSON streaming.

No external dependencies beyond `requests` (already available).
"""

import io
import json
import time
from datetime import datetime, timezone

import requests

import chess.pgn

LICHESS_API_BASE = "https://lichess.org/api"
USER_AGENT = "FischerChess/1.0 (https://github.com/fischer-chess)"


def _date_to_millis(date_str):
    """Convert YYYY-MM-DD string to millisecond timestamp for Lichess API."""
    if not date_str:
        return None
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def fetch_lichess_games(username, since_date=None, until_date=None, max_games=500):
    """Fetch games from Lichess API as NDJSON stream.

    Args:
        username: Lichess username
        since_date: optional start date as YYYY-MM-DD string
        until_date: optional end date as YYYY-MM-DD string
        max_games: maximum number of games to fetch (default 500)

    Yields:
        dict — one per game, with fields: id, rated, speed, perf, status, winner,
        players, opening, moves, clocks, analysis, createdAt, lastMoveAt
    """
    url = f"{LICHESS_API_BASE}/games/user/{username}"
    headers = {
        "Accept": "application/x-ndjson",
        "User-Agent": USER_AGENT,
    }
    params = {
        "evals": "true",
        "clocks": "true",
        "opening": "true",
        "max": str(max_games),
    }

    since_ms = _date_to_millis(since_date)
    until_ms = _date_to_millis(until_date)
    if since_ms is not None:
        params["since"] = str(since_ms)
    if until_ms is not None:
        params["until"] = str(until_ms)

    try:
        resp = requests.get(url, headers=headers, params=params, stream=True, timeout=120)
    except requests.RequestException as e:
        raise RuntimeError(f"Lichess API request failed: {e}")

    if resp.status_code == 429:
        # Rate limited — wait and retry once
        time.sleep(60)
        resp = requests.get(url, headers=headers, params=params, stream=True, timeout=120)

    if resp.status_code != 200:
        raise RuntimeError(
            f"Lichess API returned status {resp.status_code}: {resp.text[:500]}"
        )

    # Stream NDJSON line by line
    for line in resp.iter_lines(decode_unicode=True):
        if not line or not line.strip():
            continue
        try:
            game = json.loads(line)
            yield game
        except json.JSONDecodeError:
            continue


def lichess_game_to_pgn(game_dict):
    """Convert a Lichess NDJSON game dict to PGN text.

    Args:
        game_dict: dict from fetch_lichess_games()

    Returns:
        PGN string with standard headers and movetext
    """
    players = game_dict.get("players", {})
    white_info = players.get("white", {})
    black_info = players.get("black", {})

    white_name = white_info.get("user", {}).get("name", "?")
    black_name = black_info.get("user", {}).get("name", "?")
    white_rating = white_info.get("rating", "?")
    black_rating = black_info.get("rating", "?")

    # Determine result
    winner = game_dict.get("winner")
    status = game_dict.get("status", "")
    if winner == "white":
        result = "1-0"
    elif winner == "black":
        result = "0-1"
    elif status in ("draw", "stalemate"):
        result = "1/2-1/2"
    else:
        result = "*"

    # Date from createdAt (ms timestamp)
    created_at = game_dict.get("createdAt", 0)
    if created_at:
        dt = datetime.fromtimestamp(created_at / 1000, tz=timezone.utc)
        date_str = dt.strftime("%Y.%m.%d")
    else:
        date_str = "????.??.??"

    # Opening info
    opening = game_dict.get("opening", {})
    eco = opening.get("eco", "")
    opening_name = opening.get("name", "")

    # Time control
    speed = game_dict.get("speed", "")
    clock = game_dict.get("clock", {})
    if clock:
        initial = clock.get("initial", 0)
        increment = clock.get("increment", 0)
        time_control = f"{initial}+{increment}"
    else:
        time_control = "-"

    # Build PGN headers
    headers = [
        f'[Event "Lichess {speed}"]',
        f'[Site "https://lichess.org/{game_dict.get("id", "")}"]',
        f'[Date "{date_str}"]',
        f'[White "{white_name}"]',
        f'[Black "{black_name}"]',
        f'[Result "{result}"]',
        f'[WhiteElo "{white_rating}"]',
        f'[BlackElo "{black_rating}"]',
        f'[TimeControl "{time_control}"]',
    ]
    if eco:
        headers.append(f'[ECO "{eco}"]')
    if opening_name:
        headers.append(f'[Opening "{opening_name}"]')

    # Moves
    moves_str = game_dict.get("moves", "")
    if not moves_str:
        return "\n".join(headers) + f"\n\n{result}\n"

    # Format moves with move numbers
    moves = moves_str.split()
    formatted_moves = []
    for i, move in enumerate(moves):
        if i % 2 == 0:
            formatted_moves.append(f"{i // 2 + 1}. {move}")
        else:
            formatted_moves.append(move)

    movetext = " ".join(formatted_moves) + f" {result}"

    return "\n".join(headers) + "\n\n" + movetext + "\n"


def extract_lichess_evals(game_dict):
    """Extract per-move evaluation data from a Lichess game.

    Args:
        game_dict: dict from fetch_lichess_games()

    Returns:
        list of eval dicts [{eval: int_centipawns, best: uci_or_none, judgment: name_or_none}]
        or None if no analysis available
    """
    analysis = game_dict.get("analysis")
    if not analysis:
        return None

    evals = []
    for entry in analysis:
        eval_dict = {}

        if "mate" in entry:
            eval_dict["mate"] = entry["mate"]
        elif "eval" in entry:
            eval_dict["eval"] = entry["eval"]  # centipawns
        else:
            eval_dict["eval"] = 0

        if "best" in entry:
            eval_dict["best"] = entry["best"]

        judgment = entry.get("judgment", {})
        if judgment:
            eval_dict["judgment"] = judgment.get("name")

        evals.append(eval_dict)

    return evals if evals else None


def extract_clock_data(game_dict):
    """Extract per-move clock data from a Lichess game.

    Lichess clocks array contains centisecond values, alternating white/black.
    clocks[0] = white's clock after move 1, clocks[1] = black's clock after move 1, etc.

    Args:
        game_dict: dict from fetch_lichess_games()

    Returns:
        list of {"move": int, "color": str, "clock_seconds": float}
        or None if no clock data
    """
    clocks = game_dict.get("clocks")
    if not clocks:
        return None

    clock_data = []
    for i, centiseconds in enumerate(clocks):
        move_number = (i // 2) + 1
        color = "white" if i % 2 == 0 else "black"
        clock_data.append({
            "move": move_number,
            "color": color,
            "clock_seconds": centiseconds / 100.0,
        })

    return clock_data if clock_data else None


def get_lichess_game_id(game_dict):
    """Extract the unique Lichess game ID for deduplication."""
    return game_dict.get("id", "")
