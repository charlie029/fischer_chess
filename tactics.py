"""Tactic classifier — detect the type of tactic in a puzzle position."""

import chess


def classify_tactic(board, best_move):
    """Classify the tactic type of the best move in a position.
    
    Args:
        board: chess.Board BEFORE the best move is played
        best_move: chess.Move — the best (solution) move
    
    Returns:
        list of tactic tags (e.g. ["fork", "check"])
    """
    tactics = []
    turn = board.turn
    piece = board.piece_at(best_move.from_square)
    if not piece:
        return ["unknown"]

    # Play the move on a copy
    after = board.copy()
    after.push(best_move)

    is_check = after.is_check()
    is_capture = board.is_capture(best_move)
    is_promo = best_move.promotion is not None

    if is_check:
        tactics.append("check")

    if after.is_checkmate():
        tactics.append("checkmate")
        if _is_back_rank_mate(after):
            tactics.append("back rank mate")
        if _is_smothered_mate(after, best_move):
            tactics.append("smothered mate")
        return tactics  # checkmate is the whole story

    # Fork: after the move, the piece attacks 2+ higher-value or undefended pieces
    if _is_fork(after, best_move.to_square, turn):
        tactics.append("fork")

    # Discovered attack: moving piece reveals an attack from a behind piece
    if _is_discovered_attack(board, after, best_move, turn):
        tactics.append("discovered attack")
        if is_check and piece.piece_type != chess.QUEEN:
            # The check came from the revealed piece, not the moving piece
            if not after.is_attacked_by(turn, after.king(not turn)):
                pass  # moving piece doesn't give check — it's discovered check
            tactics.append("discovered check")

    # Pin exploitation: the best move exploits a pin
    if _is_pin_exploitation(board, best_move, turn):
        tactics.append("pin")

    # Skewer: piece attacks a high-value piece that must move, exposing one behind
    if _is_skewer(after, best_move.to_square, turn):
        tactics.append("skewer")

    if is_capture:
        tactics.append("capture")

    if is_promo:
        tactics.append("promotion")

    # Trapped piece: the best move traps an opponent piece
    if _is_trapping(after, turn):
        tactics.append("trapped piece")

    if not tactics:
        tactics.append("positional")

    return tactics


PIECE_VALUES = {
    chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
    chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 100,
}


def _is_fork(board, sq, attacker_color):
    """After the move, does the piece on sq attack 2+ enemy pieces worth ≥ knight?"""
    piece = board.piece_at(sq)
    if not piece:
        return False
    attacked_valuable = []
    for target_sq in board.attacks(sq):
        target = board.piece_at(target_sq)
        if target and target.color != attacker_color:
            if PIECE_VALUES.get(target.piece_type, 0) >= 3:
                attacked_valuable.append(target_sq)
    return len(attacked_valuable) >= 2


def _is_discovered_attack(before, after, move, turn):
    """Did moving the piece reveal an attack from a piece behind it?"""
    from_sq = move.from_square
    # Find pieces of our color that now attack through the vacated square
    for sq in chess.SQUARES:
        p = before.piece_at(sq)
        if not p or p.color != turn or sq == from_sq:
            continue
        # Sliding pieces only (bishop, rook, queen)
        if p.piece_type not in (chess.BISHOP, chess.ROOK, chess.QUEEN):
            continue
        # Check if this piece's attack ray passes through from_sq
        between = chess.SquareSet.between(sq, from_sq)
        # After the move, does this piece attack new squares it didn't before?
        attacks_before = before.attacks(sq)
        attacks_after = after.attacks(sq)
        new_attacks = attacks_after & ~attacks_before
        # Does it now attack an enemy piece?
        for target in new_attacks:
            t = after.piece_at(target)
            if t and t.color != turn and PIECE_VALUES.get(t.piece_type, 0) >= 3:
                return True
    return False


def _is_pin_exploitation(board, move, turn):
    """Does the best move exploit a pinned enemy piece?"""
    to_sq = move.to_square
    target = board.piece_at(to_sq)
    if target and target.color != turn:
        # Check if the captured piece was pinned
        if board.is_pinned(not turn, to_sq):
            return True
    return False


def _is_skewer(board, sq, attacker_color):
    """After the move, does the piece on sq create a skewer (attack through a valuable piece)?"""
    piece = board.piece_at(sq)
    if not piece or piece.piece_type not in (chess.BISHOP, chess.ROOK, chess.QUEEN):
        return False
    for attacked_sq in board.attacks(sq):
        target = board.piece_at(attacked_sq)
        if not target or target.color == attacker_color:
            continue
        if PIECE_VALUES.get(target.piece_type, 0) < 3:
            continue
        # Is there a piece behind the target along the same ray?
        ray = chess.SquareSet.ray(sq, attacked_sq) & ~chess.SquareSet.between(sq, attacked_sq)
        ray.discard(sq)
        ray.discard(attacked_sq)
        for behind_sq in ray:
            behind = board.piece_at(behind_sq)
            if behind and behind.color == attacker_color:
                break  # blocked by own piece
            if behind and behind.color != attacker_color:
                return True
            # empty square — continue along ray
    return False


def _is_back_rank_mate(board):
    """Is the checkmate a back rank mate?"""
    king_sq = board.king(board.turn)  # the mated king
    rank = chess.square_rank(king_sq)
    if board.turn == chess.WHITE and rank != 0:
        return False
    if board.turn == chess.BLACK and rank != 7:
        return False
    # King is on back rank and blocked by own pieces
    return True


def _is_smothered_mate(board, move):
    """Is the checkmate delivered by a knight with the king surrounded by own pieces?"""
    piece = board.piece_at(move.to_square)
    if not piece or piece.piece_type != chess.KNIGHT:
        return False
    king_sq = board.king(board.turn)
    for sq in chess.SQUARES:
        if chess.square_distance(king_sq, sq) == 1:
            p = board.piece_at(sq)
            if not p or p.color != board.turn:
                return False  # escape square or enemy piece
    return True


def _is_trapping(board, attacker_color):
    """After the move, is any enemy piece trapped (attacked and can't escape)?"""
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if not p or p.color == attacker_color or p.piece_type == chess.PAWN:
            continue
        if not board.is_attacked_by(attacker_color, sq):
            continue
        # Is the piece defended?
        if board.is_attacked_by(not attacker_color, sq):
            continue
        # Can it move to a safe square?
        has_escape = False
        for move in board.legal_moves:
            if move.from_square == sq:
                test = board.copy()
                test.push(move)
                if not test.is_attacked_by(attacker_color, move.to_square):
                    has_escape = True
                    break
        if not has_escape and PIECE_VALUES.get(p.piece_type, 0) >= 3:
            return True
    return False
