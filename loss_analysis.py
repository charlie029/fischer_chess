"""Loss Analysis Engine — classify how chess games were lost.

Analyzes games from Lichess (with server-side evals) or Chess.com (via local Stockfish).
Classifies each loss into categories: one-move blunder, gradual decline, opening disaster,
endgame collapse, time trouble, tactical sequence, or never had a chance.
"""

import io
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import chess
import chess.engine
import chess.pgn


class MoveClassification(Enum):
    """Lichess-standard move quality thresholds."""
    BEST = "best"              # <10 cp loss
    GOOD = "good"              # 10-49 cp loss
    INACCURACY = "inaccuracy"  # 50-99 cp loss
    MISTAKE = "mistake"        # 100-199 cp loss
    BLUNDER = "blunder"        # >=200 cp loss


class LossCategory(Enum):
    """How a game was lost."""
    ONE_MOVE_BLUNDER = "one_move_blunder"
    GRADUAL_DECLINE = "gradual_decline"
    OPENING_DISASTER = "opening_disaster"
    ENDGAME_COLLAPSE = "endgame_collapse"
    TIME_TROUBLE = "time_trouble"
    TACTICAL_SEQUENCE = "tactical_sequence"
    NEVER_HAD_A_CHANCE = "never_had_a_chance"


# Display names for frontend
LOSS_CATEGORY_LABELS = {
    "one_move_blunder": "One-Move Blunder",
    "gradual_decline": "Gradual Decline",
    "opening_disaster": "Opening Disaster",
    "endgame_collapse": "Endgame Collapse",
    "time_trouble": "Time Trouble",
    "tactical_sequence": "Tactical Sequence",
    "never_had_a_chance": "Never Had a Chance",
}


@dataclass
class AnalyzedMove:
    """Per-move analysis result."""
    move_number: int
    color: str  # "white" or "black"
    san: str
    eval_before: float  # in pawns, from the moving side's perspective
    eval_after: float
    cp_loss: float  # centipawn loss (>=0)
    classification: MoveClassification
    best_move_san: Optional[str] = None


@dataclass
class GameAnalysis:
    """Full analysis result for a single game."""
    result: str  # 'win', 'loss', 'draw'
    user_color: str  # 'white' or 'black'
    loss_category: Optional[str] = None  # LossCategory value or None
    loss_description: str = ""
    worst_move_number: int = 0
    worst_move_san: str = ""
    worst_move_cp_loss: int = 0
    eval_before_worst: float = 0.0
    eval_after_worst: float = 0.0
    total_blunders: int = 0
    total_mistakes: int = 0
    total_inaccuracies: int = 0
    avg_cp_loss: float = 0.0
    accuracy: float = 0.0  # 0-100
    opening_name: str = ""
    time_control: str = ""


def classify_move(cp_loss: float) -> MoveClassification:
    """Classify a move based on centipawn loss (in pawns, not centipawns)."""
    if cp_loss < 0.10:
        return MoveClassification.BEST
    elif cp_loss < 0.50:
        return MoveClassification.GOOD
    elif cp_loss < 1.00:
        return MoveClassification.INACCURACY
    elif cp_loss < 2.00:
        return MoveClassification.MISTAKE
    else:
        return MoveClassification.BLUNDER


def score_to_pawns(score, pov_color):
    """Convert engine PovScore to pawns from the given color's perspective.
    Mate scores are capped at +/-100.
    """
    relative = score.pov(pov_color)
    if relative.is_mate():
        mate_in = relative.mate()
        return 100.0 if mate_in > 0 else -100.0
    cp = relative.score()
    return cp / 100.0 if cp is not None else 0.0


def analyze_game_moves(pgn_text, engine_path=None, depth=15, lichess_evals=None):
    """Analyze every move in a game and return per-move analysis.

    Args:
        pgn_text: PGN string of the game
        engine_path: path to Stockfish binary (not needed if lichess_evals provided)
        depth: Stockfish search depth
        lichess_evals: list of per-move eval dicts from Lichess API, e.g.
            [{"eval": 30}, {"eval": -10, "best": "d7d5", "judgment": {"name": "Inaccuracy"}}]
            eval is in centipawns. If a move has "mate" instead of "eval", it's a mate score.

    Returns:
        list of AnalyzedMove objects
    """
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if not game:
        return []

    board = game.board()
    analyzed = []
    engine = None

    if lichess_evals and len(lichess_evals) > 0:
        # Use Lichess server-side evals
        moves_list = list(game.mainline())
        # Lichess analysis array has one entry per ply (half-move)
        # Entry 0 = eval after move 1 by white, etc.
        # We need eval BEFORE each move, so we shift by one

        # Initial position eval: use first entry's eval as "before first move"
        # Actually, Lichess evals[i] = eval AFTER ply i (0-indexed)
        # So eval before ply 0 = starting position (assumed ~0)
        # eval after ply 0 = evals[0]
        prev_eval_white = 0.0  # starting position, white's perspective

        for ply, node in enumerate(moves_list):
            move = node.move
            san = board.san(move)
            color = "white" if board.turn == chess.WHITE else "black"
            side = board.turn

            eval_before_side = prev_eval_white if side == chess.WHITE else -prev_eval_white

            # Get eval after this move from Lichess data
            if ply < len(lichess_evals):
                entry = lichess_evals[ply]
                if "mate" in entry:
                    mate_val = entry["mate"]
                    eval_after_white = 100.0 if mate_val > 0 else -100.0
                else:
                    eval_after_white = entry.get("eval", 0) / 100.0
            else:
                eval_after_white = prev_eval_white  # fallback

            eval_after_side = eval_after_white if side == chess.WHITE else -eval_after_white

            # CP loss from the moving side's perspective
            cp_loss = max(0, eval_before_side - eval_after_side)

            best_san = None
            if ply < len(lichess_evals):
                best_uci = lichess_evals[ply].get("best")
                if best_uci:
                    try:
                        best_move = chess.Move.from_uci(best_uci)
                        best_san = board.san(best_move)
                    except (ValueError, chess.IllegalMoveError):
                        pass

            analyzed.append(AnalyzedMove(
                move_number=(ply // 2) + 1,
                color=color,
                san=san,
                eval_before=round(eval_before_side, 2),
                eval_after=round(eval_after_side, 2),
                cp_loss=round(cp_loss, 2),
                classification=classify_move(cp_loss),
                best_move_san=best_san,
            ))

            board.push(move)
            prev_eval_white = eval_after_white

    else:
        # Use local Stockfish
        if not engine_path:
            from puzzles import download_stockfish
            engine_path = download_stockfish()

        engine = chess.engine.SimpleEngine.popen_uci(engine_path)
        engine.configure({"Hash": 64, "Threads": 1})

        try:
            # Evaluate starting position
            info = engine.analyse(board, chess.engine.Limit(depth=depth))
            prev_eval_white = score_to_pawns(info["score"], chess.WHITE)

            for ply, node in enumerate(game.mainline()):
                move = node.move
                san = board.san(move)
                color = "white" if board.turn == chess.WHITE else "black"
                side = board.turn

                eval_before_side = prev_eval_white if side == chess.WHITE else -prev_eval_white

                # Get best move before playing
                best_info = engine.analyse(board, chess.engine.Limit(depth=depth))
                pv = best_info.get("pv", [])
                best_san = board.san(pv[0]) if pv else None

                # Play the move
                board.push(move)

                # Evaluate after
                info = engine.analyse(board, chess.engine.Limit(depth=depth))
                eval_after_white = score_to_pawns(info["score"], chess.WHITE)
                eval_after_side = eval_after_white if side == chess.WHITE else -eval_after_white

                cp_loss = max(0, eval_before_side - eval_after_side)

                analyzed.append(AnalyzedMove(
                    move_number=(ply // 2) + 1,
                    color=color,
                    san=san,
                    eval_before=round(eval_before_side, 2),
                    eval_after=round(eval_after_side, 2),
                    cp_loss=round(cp_loss, 2),
                    classification=classify_move(cp_loss),
                    best_move_san=best_san,
                ))

                prev_eval_white = eval_after_white
        finally:
            engine.quit()

    return analyzed


def classify_loss(move_analyses, loser_color, clock_data=None):
    """Classify how a player lost based on their move quality trajectory.

    Args:
        move_analyses: list of AnalyzedMove from analyze_game_moves()
        loser_color: "white" or "black"
        clock_data: optional list of {"move": int, "color": str, "clock_seconds": float}

    Returns:
        (LossCategory, description_string)
    """
    if not move_analyses:
        return LossCategory.GRADUAL_DECLINE, "No moves to analyze"

    loser_moves = [m for m in move_analyses if m.color == loser_color]
    if not loser_moves:
        return LossCategory.GRADUAL_DECLINE, "No moves from losing side"

    # Eval trajectory for the loser (from their perspective)
    evals = [m.eval_before for m in loser_moves]
    if loser_moves:
        evals.append(loser_moves[-1].eval_after)

    # Find worst move and blunders
    worst_move = max(loser_moves, key=lambda m: m.cp_loss)
    blunders = [m for m in loser_moves if m.classification == MoveClassification.BLUNDER]

    total_moves = len(loser_moves)
    opening_end = min(15, total_moves)
    endgame_start = max(total_moves - 15, opening_end)

    # --- Time trouble check (requires clock data) ---
    if clock_data:
        loser_clocks = sorted(
            [c for c in clock_data if c["color"] == loser_color],
            key=lambda c: c["move"]
        )
        if loser_clocks:
            final_clock = loser_clocks[-1]["clock_seconds"]
            late_blunders_under_time = [
                m for m in blunders
                if m.move_number > total_moves - 10
                and any(
                    c["clock_seconds"] < 30 and c["move"] == m.move_number
                    for c in loser_clocks
                )
            ]
            if final_clock < 10 or len(late_blunders_under_time) >= 2:
                return (
                    LossCategory.TIME_TROUBLE,
                    f"Lost under time pressure ({len(late_blunders_under_time)} "
                    f"blunders with <30s remaining, final clock: {final_clock:.0f}s)"
                )

    # --- Never had a chance: losing from the start ---
    if len(evals) >= 5 and all(e < -1.0 for e in evals[:5]) and evals[0] < -1.5:
        return (
            LossCategory.NEVER_HAD_A_CHANCE,
            "Was losing from the very start of the game"
        )

    # --- Opening disaster: blunder in first 15 moves ---
    opening_moves = [m for m in loser_moves if m.move_number <= 15]
    opening_blunders = [m for m in opening_moves if m.cp_loss >= 2.0]
    if opening_blunders and len(evals) > opening_end and min(evals[:opening_end + 1]) < -2.0:
        worst_opening = max(opening_blunders, key=lambda m: m.cp_loss)
        return (
            LossCategory.OPENING_DISASTER,
            f"Lost in the opening: {worst_opening.san} on move {worst_opening.move_number} "
            f"(lost {worst_opening.cp_loss:.1f} pawns)"
        )

    # --- One-move blunder: single move >= 3.0 pawn loss from a reasonable position ---
    if worst_move.cp_loss >= 3.0 and worst_move.eval_before >= -1.0:
        return (
            LossCategory.ONE_MOVE_BLUNDER,
            f"Game decided by a single blunder: {worst_move.san} on move "
            f"{worst_move.move_number} (lost {worst_move.cp_loss:.1f} pawns, "
            f"eval {worst_move.eval_before:+.1f} to {worst_move.eval_after:+.1f})"
        )

    # --- Tactical sequence: 2+ blunders within 5 moves of each other ---
    if len(blunders) >= 2:
        for i in range(len(blunders) - 1):
            if blunders[i + 1].move_number - blunders[i].move_number <= 5:
                return (
                    LossCategory.TACTICAL_SEQUENCE,
                    f"Lost through a sequence of {len(blunders)} tactical errors "
                    f"(moves {blunders[0].move_number} to {blunders[-1].move_number})"
                )

    # --- Endgame collapse: position was OK at midgame, errors in the final phase ---
    endgame_moves = [m for m in loser_moves if m.move_number >= endgame_start]
    endgame_blunders = [m for m in endgame_moves if m.cp_loss >= 1.5]
    mid_idx = len(evals) // 2
    mid_eval = evals[mid_idx] if mid_idx < len(evals) else 0
    if mid_eval >= -1.0 and endgame_blunders and evals[-1] < -2.0:
        return (
            LossCategory.ENDGAME_COLLAPSE,
            f"Position was holdable (eval {mid_eval:+.1f} at midgame) "
            f"but collapsed in the endgame with {len(endgame_blunders)} error(s)"
        )

    # --- Gradual decline: default ---
    inaccuracies = [
        m for m in loser_moves
        if m.classification in (MoveClassification.INACCURACY, MoveClassification.MISTAKE)
    ]
    return (
        LossCategory.GRADUAL_DECLINE,
        f"Gradually outplayed over {total_moves} moves "
        f"({len(inaccuracies)} inaccuracies/mistakes, {len(blunders)} blunder(s)). "
        f"Eval drifted from {evals[0]:+.1f} to {evals[-1]:+.1f}"
    )


def analyze_game_for_loss(pgn_text, username, lichess_evals=None,
                          clock_data=None, engine_path=None, depth=15):
    """Full analysis of a single game: determine result, classify loss, compute stats.

    Args:
        pgn_text: PGN string
        username: the player's username (matched against White/Black headers)
        lichess_evals: optional Lichess server-side evals
        clock_data: optional clock data for time trouble detection
        engine_path: Stockfish binary path
        depth: analysis depth

    Returns:
        GameAnalysis dataclass
    """
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if not game:
        return GameAnalysis(result="unknown", user_color="unknown")

    headers = game.headers
    white = headers.get("White", "?")
    black = headers.get("Black", "?")
    result_str = headers.get("Result", "*")
    opening = headers.get("Opening", headers.get("ECO", ""))
    time_control = headers.get("TimeControl", "")

    # Determine user's color
    uname_lower = username.lower()
    if uname_lower in white.lower():
        user_color = "white"
    elif uname_lower in black.lower():
        user_color = "black"
    else:
        # Fallback: try exact match
        user_color = "white" if uname_lower == white.lower() else "black"

    # Determine result from user's perspective
    if result_str == "1-0":
        result = "win" if user_color == "white" else "loss"
    elif result_str == "0-1":
        result = "win" if user_color == "black" else "loss"
    elif result_str == "1/2-1/2":
        result = "draw"
    else:
        result = "unknown"

    analysis = GameAnalysis(
        result=result,
        user_color=user_color,
        opening_name=opening,
        time_control=time_control,
    )

    # Only do deep analysis for losses (and optionally draws)
    if result != "loss":
        return analysis

    # Analyze all moves
    move_analyses = analyze_game_moves(
        pgn_text, engine_path=engine_path, depth=depth, lichess_evals=lichess_evals
    )

    if not move_analyses:
        analysis.loss_description = "Could not analyze moves"
        return analysis

    # Classify the loss
    category, description = classify_loss(move_analyses, user_color, clock_data)
    analysis.loss_category = category.value
    analysis.loss_description = description

    # Compute stats for the user's moves
    user_moves = [m for m in move_analyses if m.color == user_color]
    if user_moves:
        worst = max(user_moves, key=lambda m: m.cp_loss)
        analysis.worst_move_number = worst.move_number
        analysis.worst_move_san = worst.san
        analysis.worst_move_cp_loss = int(worst.cp_loss * 100)  # store as centipawns
        analysis.eval_before_worst = worst.eval_before
        analysis.eval_after_worst = worst.eval_after

        analysis.total_blunders = sum(
            1 for m in user_moves if m.classification == MoveClassification.BLUNDER
        )
        analysis.total_mistakes = sum(
            1 for m in user_moves if m.classification == MoveClassification.MISTAKE
        )
        analysis.total_inaccuracies = sum(
            1 for m in user_moves if m.classification == MoveClassification.INACCURACY
        )

        cp_losses = [m.cp_loss for m in user_moves]
        analysis.avg_cp_loss = round(sum(cp_losses) / len(cp_losses), 2) if cp_losses else 0

        # Accuracy: higher is better, scale so 0 cp_loss = 100%, ~2.0 avg = ~0%
        # Formula: 100 * max(0, 1 - avg_cp_loss / 2.0), clamped to 0-100
        raw_accuracy = 100.0 * max(0, 1.0 - analysis.avg_cp_loss / 2.0)
        analysis.accuracy = round(min(100.0, max(0.0, raw_accuracy)), 1)

    return analysis
