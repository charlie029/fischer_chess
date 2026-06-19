"""Player stats — summarize blunders/misses by tactic type from puzzle PGN files."""

import json
import os
import chess
import chess.pgn
from tactics import classify_tactic

STATS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "player_stats")


def analyze_puzzle_tactics(pgn_path):
    """Read a puzzle PGN and classify each puzzle's tactic type.
    
    Returns list of dicts with puzzle info + tactics.
    """
    results = []
    with open(pgn_path) as f:
        while True:
            game = chess.pgn.read_game(f)
            if game is None:
                break
            h = game.headers
            fen = h.get("FEN", chess.STARTING_FEN)
            board = chess.Board(fen)
            mainline = list(game.mainline())
            if not mainline:
                continue
            best_move = mainline[0].move
            tactics = classify_tactic(board, best_move)
            results.append({
                "white": h.get("White", "?"),
                "black": h.get("Black", "?"),
                "event": h.get("Event", "?"),
                "date": h.get("Date", "?"),
                "move_number": h.get("PuzzleMove", ""),
                "turn": h.get("PuzzleTurn", "white"),
                "reason": h.get("PuzzleReason", ""),
                "best_move": board.san(best_move),
                "comment": mainline[0].comment,
                "tactics": tactics,
                "fen": fen,
            })
    return results


def build_player_stats(puzzles, player_name):
    """Build stats summary for a specific player from classified puzzles.
    
    A puzzle counts for a player if they were the one who blundered
    (i.e., it was their turn and they missed the best move).
    """
    pl = player_name.lower()
    player_puzzles = []
    for p in puzzles:
        # The blunderer is the player whose turn it was
        if p["turn"] == "white" and pl in p["white"].lower():
            player_puzzles.append(p)
        elif p["turn"] == "black" and pl in p["black"].lower():
            player_puzzles.append(p)

    if not player_puzzles:
        return None

    tactic_counts = {}
    by_game = {}
    blunder_sizes = []

    for p in player_puzzles:
        for t in p["tactics"]:
            tactic_counts[t] = tactic_counts.get(t, 0) + 1
        game_key = f"{p['white']} vs {p['black']} ({p['date']})"
        by_game.setdefault(game_key, []).append({
            "move": p["move_number"],
            "reason": p["reason"],
            "best_move": p["best_move"],
            "tactics": p["tactics"],
        })
        # Extract cp drop from reason
        import re
        m = re.search(r"−(\d+)cp", p["reason"])
        if m:
            blunder_sizes.append(int(m.group(1)))

    avg_drop = round(sum(blunder_sizes) / len(blunder_sizes)) if blunder_sizes else 0

    return {
        "player": player_name,
        "total_blunders": len(player_puzzles),
        "avg_cp_loss": avg_drop,
        "tactic_breakdown": dict(sorted(tactic_counts.items(), key=lambda x: -x[1])),
        "by_game": by_game,
        "puzzles": [{
            "move": p["move_number"],
            "reason": p["reason"],
            "best_move": p["best_move"],
            "tactics": p["tactics"],
            "fen": p["fen"],
        } for p in player_puzzles],
    }


def save_player_stats(stats, source_pgn):
    """Save player stats to a JSON file in player_stats/."""
    os.makedirs(STATS_DIR, exist_ok=True)
    safe_name = stats["player"].replace(" ", "_").lower()
    path = os.path.join(STATS_DIR, f"{safe_name}.json")

    # Load existing data and merge
    existing = {}
    if os.path.isfile(path):
        with open(path) as f:
            existing = json.load(f)

    # Key by source file to allow re-runs
    existing.setdefault("player", stats["player"])
    existing.setdefault("sources", {})
    existing["sources"][os.path.basename(source_pgn)] = stats

    # Compute aggregate across all sources
    total = 0
    all_tactics = {}
    all_drops = []
    for src_stats in existing["sources"].values():
        total += src_stats["total_blunders"]
        for t, c in src_stats["tactic_breakdown"].items():
            all_tactics[t] = all_tactics.get(t, 0) + c
        all_drops.extend([p.get("avg_cp_loss", 0)] for p in [src_stats])

    existing["aggregate"] = {
        "total_blunders": total,
        "tactic_breakdown": dict(sorted(all_tactics.items(), key=lambda x: -x[1])),
        "sources_count": len(existing["sources"]),
    }

    with open(path, "w") as f:
        json.dump(existing, f, indent=2)

    return path


def generate_stats_for_file(pgn_path, player_name=None):
    """Main entry: classify tactics in a puzzle PGN and save stats.
    
    If player_name is given, only that player's stats are saved.
    Otherwise, stats for all players found in the puzzles are saved.
    """
    puzzles = analyze_puzzle_tactics(pgn_path)
    if not puzzles:
        return []

    # Find all unique players
    if player_name:
        players = [player_name]
    else:
        names = set()
        for p in puzzles:
            names.add(p["white"])
            names.add(p["black"])
        names.discard("?")
        players = sorted(names)

    saved = []
    for name in players:
        stats = build_player_stats(puzzles, name)
        if stats:
            path = save_player_stats(stats, pgn_path)
            saved.append((name, stats, path))

    return saved
