"""
Extracts human-readable position features from a FEN string using python-chess.
These features ground Claude's explanations in verifiable board state.
"""
from collections import Counter
from dataclasses import dataclass, field

import chess


@dataclass
class PositionFeatures:
    material_balance: str
    king_safety: str
    pawn_structure: str
    piece_activity: str
    tactical_motifs: list[str]
    open_files: list[str]


_PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
}


def analyze_position(fen: str) -> PositionFeatures:
    board = chess.Board(fen)
    return PositionFeatures(
        material_balance=_material_balance(board),
        king_safety=_king_safety(board),
        pawn_structure=_pawn_structure(board),
        piece_activity=_piece_activity(board),
        tactical_motifs=_tactical_motifs(board),
        open_files=_open_files(board),
    )


def _material_balance(board: chess.Board) -> str:
    white = sum(
        _PIECE_VALUES.get(p.piece_type, 0)
        for p in board.piece_map().values()
        if p.color == chess.WHITE
    )
    black = sum(
        _PIECE_VALUES.get(p.piece_type, 0)
        for p in board.piece_map().values()
        if p.color == chess.BLACK
    )
    diff = white - black
    if diff == 0:
        return "Material is equal"
    side = "White" if diff > 0 else "Black"
    pts = abs(diff)
    return f"{side} is up {pts} material point{'s' if pts > 1 else ''}"


def _king_safety(board: chess.Board) -> str:
    parts = []
    for color in (chess.WHITE, chess.BLACK):
        name = "White" if color == chess.WHITE else "Black"
        king_sq = board.king(color)
        if king_sq is None:
            continue

        in_check = bool(board.attackers(not color, king_sq))
        king_file = chess.square_file(king_sq)
        king_rank = chess.square_rank(king_sq)

        # Count pawn shield (one rank ahead)
        forward_rank = king_rank + (1 if color == chess.WHITE else -1)
        shield = 0
        if 0 <= forward_rank <= 7:
            for f in range(max(0, king_file - 1), min(8, king_file + 2)):
                piece = board.piece_at(chess.square(f, forward_rank))
                if piece and piece.piece_type == chess.PAWN and piece.color == color:
                    shield += 1

        uncastled = (color == chess.WHITE and king_sq == chess.E1) or (
            color == chess.BLACK and king_sq == chess.E8
        )

        if in_check:
            parts.append(f"{name} king in check")
        elif uncastled:
            parts.append(f"{name} king: uncastled ({shield} pawn shield)")
        elif shield == 0:
            parts.append(f"{name} king: castled but no pawn shield — exposed")
        else:
            parts.append(f"{name} king: safe ({shield} pawn shield)")
    return "; ".join(parts)


def _pawn_structure(board: chess.Board) -> str:
    issues = []
    for color in (chess.WHITE, chess.BLACK):
        name = "White" if color == chess.WHITE else "Black"
        files = [
            chess.square_file(sq)
            for sq in chess.SQUARES
            if (p := board.piece_at(sq)) and p.piece_type == chess.PAWN and p.color == color
        ]
        if not files:
            continue

        # Doubled pawns
        counts = Counter(files)
        doubled = [chess.FILE_NAMES[f] for f, c in counts.items() if c > 1]
        if doubled:
            issues.append(f"{name} doubled pawns on {'/'.join(doubled)}-file")

        # Isolated pawns
        isolated = [
            chess.FILE_NAMES[f]
            for f in set(files)
            if not any(n in files for n in (f - 1, f + 1) if 0 <= n <= 7)
        ]
        if isolated:
            issues.append(f"{name} isolated pawn(s) on {'/'.join(isolated)}-file")

    return "; ".join(issues) if issues else "No major pawn structure weaknesses"


def _piece_activity(board: chess.Board) -> str:
    white_moves = len(list(board.generate_legal_moves())) if board.turn == chess.WHITE else 0
    b = board.copy()
    b.turn = chess.BLACK if board.turn == chess.WHITE else chess.WHITE
    black_moves = len(list(b.generate_legal_moves()))
    if board.turn == chess.BLACK:
        white_moves, black_moves = black_moves, white_moves  # recalculate correctly
        b2 = board.copy()
        b2.turn = chess.WHITE
        white_moves = len(list(b2.generate_legal_moves()))
        black_moves = len(list(board.generate_legal_moves()))

    if white_moves > black_moves + 5:
        return f"White pieces more active ({white_moves} vs {black_moves} legal moves)"
    if black_moves > white_moves + 5:
        return f"Black pieces more active ({black_moves} vs {white_moves} legal moves)"
    return f"Roughly equal piece activity ({white_moves} vs {black_moves} legal moves)"


def _tactical_motifs(board: chess.Board) -> list[str]:
    motifs = []

    # Hanging pieces
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece and piece.piece_type != chess.KING:
            attackers = board.attackers(not piece.color, sq)
            defenders = board.attackers(piece.color, sq)
            if attackers and not defenders:
                name = "White" if piece.color == chess.WHITE else "Black"
                motifs.append(
                    f"{name}'s {chess.piece_name(piece.piece_type).capitalize()} on "
                    f"{chess.square_name(sq)} is hanging (undefended)"
                )

    # Pinned pieces
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece and piece.piece_type not in (chess.KING, chess.PAWN):
            if board.is_pinned(piece.color, sq):
                motifs.append(
                    f"{chess.piece_name(piece.piece_type).capitalize()} on "
                    f"{chess.square_name(sq)} is pinned"
                )

    # Back-rank weakness
    for color in (chess.WHITE, chess.BLACK):
        back_rank = 0 if color == chess.WHITE else 7
        king_sq = board.king(color)
        if king_sq and chess.square_rank(king_sq) == back_rank:
            for att_sq in board.pieces(chess.ROOK, not color) | board.pieces(chess.QUEEN, not color):
                if chess.square_rank(att_sq) == back_rank:
                    name = "White" if color == chess.WHITE else "Black"
                    motifs.append(f"Potential back-rank weakness for {name}")
                    break

    return motifs[:5]


def _open_files(board: chess.Board) -> list[str]:
    results = []
    for f in range(8):
        fname = chess.FILE_NAMES[f]
        has_w = any(
            (p := board.piece_at(chess.square(f, r))) and p.piece_type == chess.PAWN and p.color == chess.WHITE
            for r in range(8)
        )
        has_b = any(
            (p := board.piece_at(chess.square(f, r))) and p.piece_type == chess.PAWN and p.color == chess.BLACK
            for r in range(8)
        )
        if not has_w and not has_b:
            results.append(f"{fname}-file (open)")
        elif not has_w or not has_b:
            results.append(f"{fname}-file (semi-open)")
    return results
