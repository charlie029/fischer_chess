#!/usr/bin/env python3
"""Chess Puzzle Generator — extract blunders and missed tactics from PGN files."""

import argparse
import os
import platform
import stat
import sys
import tarfile
import urllib.request
import zipfile

import chess
import chess.engine
import chess.pgn
from tactics import classify_tactic

STOCKFISH_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stockfish")
DEFAULT_THRESHOLD = 200
DEFAULT_DEPTH = 18


def get_stockfish_url():
    system = platform.system()
    machine = platform.machine()
    if system == "Darwin":
        return "https://github.com/official-stockfish/Stockfish/releases/latest/download/stockfish-macos-m1-apple-silicon.tar"
    elif system == "Linux":
        return "https://github.com/official-stockfish/Stockfish/releases/latest/download/stockfish-ubuntu-x86-64-avx2.tar"
    elif system == "Windows":
        return "https://github.com/official-stockfish/Stockfish/releases/latest/download/stockfish-windows-x86-64-avx2.zip"
    else:
        sys.exit(f"Unsupported platform: {system} {machine}")


def find_stockfish_binary(directory):
    for root, _, files in os.walk(directory):
        for f in files:
            if f.startswith("stockfish"):
                path = os.path.join(root, f)
                if os.access(path, os.X_OK) or f.endswith(".exe"):
                    return path
    return None


def download_stockfish():
    os.makedirs(STOCKFISH_DIR, exist_ok=True)
    existing = find_stockfish_binary(STOCKFISH_DIR)
    if existing:
        return existing

    url = get_stockfish_url()
    print(f"Downloading Stockfish from {url}...")
    data, _ = urllib.request.urlretrieve(url)

    if url.endswith(".tar"):
        with tarfile.open(data) as tf:
            tf.extractall(STOCKFISH_DIR)
    elif url.endswith(".zip"):
        with zipfile.ZipFile(data) as zf:
            zf.extractall(STOCKFISH_DIR)

    binary = find_stockfish_binary(STOCKFISH_DIR)
    if binary is None:
        sys.exit("Could not find stockfish binary after extraction.")
    os.chmod(binary, os.stat(binary).st_mode | stat.S_IEXEC)
    print(f"Stockfish ready: {binary}")
    return binary


def evaluate(engine, board, depth):
    info = engine.analyse(board, chess.engine.Limit(depth=depth))
    score = info["score"].white()
    return score


def score_to_cp(score):
    """Convert score to centipawns from white's perspective. Mate scores become large values."""
    if score.is_mate():
        m = score.mate()
        return 30000 if m > 0 else -30000
    return score.score()


def is_missed_mate(score_before, score_after, turn):
    """Check if player had a forced mate but played a move that loses the mate entirely.
    
    Not flagged when:
    - The played move is checkmate (mate()==0)
    - The played move still leads to mate (alternative/slower mate)
    - The position is still overwhelmingly winning (>500cp) — engine may just not
      see the mate at the given depth
    """
    if turn == chess.WHITE:
        had_mate = score_before.is_mate() and score_before.mate() > 0
        still_mate = score_after.is_mate() and score_after.mate() >= 0
        still_winning = not score_after.is_mate() and (score_after.score() or 0) > 500
    else:
        had_mate = score_before.is_mate() and score_before.mate() < 0
        still_mate = score_after.is_mate() and score_after.mate() <= 0
        still_winning = not score_after.is_mate() and (score_after.score() or 0) < -500
    return had_mate and not still_mate and not still_winning


def analyze_game(engine, game, threshold, depth):
    puzzles = []
    board = game.board()
    node = game

    prev_score = evaluate(engine, board, depth)

    for move_num, node in enumerate(game.mainline()):
        turn = board.turn
        board.push(node.move)
        curr_score = evaluate(engine, board, depth)

        prev_cp = score_to_cp(prev_score)
        curr_cp = score_to_cp(curr_score)

        # Eval drop from the moving side's perspective
        if turn == chess.WHITE:
            drop = prev_cp - curr_cp
        else:
            drop = curr_cp - prev_cp

        missed_mate = is_missed_mate(prev_score, curr_score, turn)

        if drop >= threshold or missed_mate:
            # Puzzle position is BEFORE the blunder move
            puzzle_board = board.copy()
            puzzle_board.pop()

            # Get best move and acceptable alternatives via MultiPV
            n_legal = sum(1 for _ in puzzle_board.legal_moves)
            mpv = min(n_legal, 5)
            infos = engine.analyse(puzzle_board, chess.engine.Limit(depth=depth), multipv=mpv)
            best_move = infos[0]["pv"][0]
            best_cp = score_to_cp(infos[0]["score"].white())
            acceptable = []
            for info in infos[1:]:
                cp = score_to_cp(info["score"].white())
                loss = (best_cp - cp) if turn == chess.WHITE else (cp - best_cp)
                if loss <= 50:
                    acceptable.append(info["pv"][0].uci())

            reason = "missed mate" if missed_mate else f"blunder (−{drop}cp)"
            tactics = classify_tactic(puzzle_board, best_move)
            puzzles.append({
                "fen": puzzle_board.fen(),
                "best_move": puzzle_board.san(best_move),
                "best_move_uci": best_move.uci(),
                "acceptable_uci": acceptable,
                "played": puzzle_board.san(node.move),
                "drop": drop,
                "reason": reason,
                "game": game.headers.get("White", "?") + " vs " + game.headers.get("Black", "?"),
                "game_info": dict(game.headers),
                "move_number": (move_num // 2) + 1,
                "turn": "white" if turn == chess.WHITE else "black",
                "tactics": tactics,
            })

        prev_score = curr_score

    return puzzles


def main():
    parser = argparse.ArgumentParser(description="Generate chess puzzles from PGN files.")
    parser.add_argument("pgn", help="Path to PGN file (can contain multiple games)")
    parser.add_argument("-o", "--output", default="puzzles.pgn", help="Output file (default: puzzles.pgn)")
    parser.add_argument("-t", "--threshold", type=int, default=DEFAULT_THRESHOLD, help=f"Blunder threshold in centipawns (default: {DEFAULT_THRESHOLD})")
    parser.add_argument("-d", "--depth", type=int, default=DEFAULT_DEPTH, help=f"Engine search depth (default: {DEFAULT_DEPTH})")
    parser.add_argument("-p", "--player", help="Only include blunders by this player (matches White/Black header, case-insensitive)")
    parser.add_argument("--stockfish", help="Path to Stockfish binary (auto-downloads if not provided)")
    args = parser.parse_args()

    stockfish_path = args.stockfish or download_stockfish()
    engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)

    all_puzzles = []
    try:
        with open(args.pgn) as f:
            game_num = 0
            while True:
                game = chess.pgn.read_game(f)
                if game is None:
                    break
                game_num += 1
                white = game.headers.get("White", "?")
                black = game.headers.get("Black", "?")

                # Determine which side(s) to focus on
                player_color = None
                if args.player:
                    pl = args.player.lower()
                    if pl in white.lower():
                        player_color = "white"
                    elif pl in black.lower():
                        player_color = "black"
                    else:
                        print(f"Skipping game {game_num}: {white} vs {black} (player not found)")
                        continue

                print(f"Analyzing game {game_num}: {white} vs {black}...")
                puzzles = analyze_game(engine, game, args.threshold, args.depth)
                if player_color:
                    puzzles = [p for p in puzzles if p["turn"] == player_color]
                game_moves = sum(1 for _ in game.mainline())
                for p in puzzles:
                    p["game_moves"] = game_moves
                print(f"  Found {len(puzzles)} puzzle(s)")
                all_puzzles.extend(puzzles)
    finally:
        engine.quit()

    # Write output as PGN
    if all_puzzles:
        with open(args.output, "w") as f:
            for i, p in enumerate(all_puzzles, 1):
                game = chess.pgn.Game()
                gi = p["game_info"]
                game.headers["Event"] = gi.get("Event", "?")
                game.headers["Site"] = gi.get("Site", "?")
                game.headers["Date"] = gi.get("Date", "????.??.??")
                game.headers["Round"] = gi.get("Round", "?")
                game.headers["White"] = gi.get("White", "?")
                game.headers["Black"] = gi.get("Black", "?")
                game.headers["Result"] = gi.get("Result", "*")
                game.headers["FEN"] = p["fen"]
                game.headers["SetUp"] = "1"
                game.headers["PuzzleNumber"] = str(i)
                game.headers["PuzzleReason"] = p["reason"]
                game.headers["PuzzleMove"] = str(p["move_number"])
                game.headers["PuzzleTurn"] = p["turn"]
                if p.get("acceptable_uci"):
                    game.headers["PuzzleAcceptable"] = ",".join(p["acceptable_uci"])
                if p.get("tactics"):
                    game.headers["PuzzleTactics"] = ",".join(p["tactics"])
                if p.get("game_moves"):
                    game.headers["GameMoves"] = str(p["game_moves"])

                board = chess.Board(p["fen"])
                node = game.add_variation(board.parse_san(p["best_move"]))
                node.comment = f"Played was {p['played']} ({p['reason']})"

                print(game, file=f)
                print(file=f)
        print(f"\n✅ {len(all_puzzles)} puzzles saved to {args.output}")
    else:
        print("\nNo blunders or missed tactics found.")


if __name__ == "__main__":
    main()
