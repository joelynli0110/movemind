"""
Stockfish-based game analysis.

Two-pass strategy:
  1. Quick pass (depth 12) over all player moves to find eval drops.
  2. Return top 3 critical moments with detailed position data.
"""
import io
import os
from dataclasses import dataclass, field
from typing import Optional

import chess
import chess.pgn

try:
    from stockfish import Stockfish as _SF
    _STOCKFISH_AVAILABLE = True
except ImportError:
    _STOCKFISH_AVAILABLE = False

STOCKFISH_PATH = os.getenv("STOCKFISH_PATH", "stockfish").strip('"').strip("'")
QUICK_DEPTH = int(os.getenv("STOCKFISH_DEPTH", "8"))
MAX_ANALYZED_PLAYER_MOVES = int(os.getenv("MAX_ANALYZED_PLAYER_MOVES", "30"))
EVALUATE_BEST_MOVE = os.getenv("STOCKFISH_EVALUATE_BEST_MOVE", "false").lower() == "true"
MIN_CRITICAL_EVAL_LOSS = int(os.getenv("MIN_CRITICAL_EVAL_LOSS", "100"))
ENGINE_CANDIDATE_LINES = int(os.getenv("ENGINE_CANDIDATE_LINES", "3"))
ENGINE_PV_MAX_MOVES = int(os.getenv("ENGINE_PV_MAX_MOVES", "6"))

# Severity labels based on eval loss (centipawns)
def eval_severity(cp: int) -> str:
    if cp >= 300: return "blunder"
    if cp >= 100: return "mistake"
    if cp >= 50:  return "inaccuracy"
    return "slight"


@dataclass
class CandidateLine:
    move: str                 # SAN
    line: list[str] = field(default_factory=list)
    centipawn: Optional[int] = None
    mate: Optional[int] = None


@dataclass
class MoveAnalysis:
    move_index: int          # 0-based index in moves_san list
    move_number: int         # Full-move number (1, 2, 3…)
    color: str               # "white" | "black"
    player_move: str         # SAN
    best_move: str           # SAN
    fen_before: str
    eval_before: int         # centipawns, White perspective
    eval_after_player: int   # centipawns, White perspective
    eval_after_best: int     # centipawns, White perspective
    eval_loss: int           # always positive: how much worse the player's move was
    pv_moves: list[str] = field(default_factory=list)
    candidate_lines: list[CandidateLine] = field(default_factory=list)

    @property
    def severity(self) -> str:
        return eval_severity(self.eval_loss)


@dataclass
class GameData:
    moves_san: list[str]
    fens: list[str]          # fens[0] = start, fens[i] = after moves_san[i-1]
    player_color: str
    headers: dict
    critical_moments: list[MoveAnalysis]  # mistake moves only (for LLM + display)
    all_analyzed: list[MoveAnalysis]       # every evaluated player move, sorted by eval_loss
    total_moves: int


class EngineAnalyst:
    def __init__(self):
        self._sf: Optional[_SF] = None
        if _STOCKFISH_AVAILABLE:
            try:
                self._sf = _SF(
                    path=STOCKFISH_PATH,
                    depth=QUICK_DEPTH,
                    parameters={"Threads": 2, "Hash": 128},
                )
            except Exception as e:
                print(f"[engine] Stockfish init failed: {e}")

    # ------------------------------------------------------------------
    def analyze_game(self, pgn_text: str, player_name: Optional[str] = None) -> GameData:
        game = chess.pgn.read_game(io.StringIO(pgn_text))
        if game is None:
            raise ValueError("Could not parse PGN")

        headers = dict(game.headers)
        player_color = _detect_color(headers, player_name)

        board = game.board()
        moves_san: list[str] = []
        fens: list[str] = [board.fen()]
        all_analyzed: list[MoveAnalysis] = []   # every player move Stockfish evaluated

        for idx, move in enumerate(game.mainline_moves()):
            san = board.san(move)
            moves_san.append(san)

            is_player = (
                (board.turn == chess.WHITE and player_color == "white") or
                (board.turn == chess.BLACK and player_color == "black")
            )

            if self._sf and is_player and len(all_analyzed) < MAX_ANALYZED_PLAYER_MOVES:
                analysis = self._analyze_single_move(board, move, san, idx)
                if analysis is not None:
                    all_analyzed.append(analysis)

            board.push(move)
            fens.append(board.fen())

        # Always surface the top 3 worst moves — even if they're small inaccuracies.
        # Sorted descending by eval_loss; then re-sort chronologically for display.
        all_analyzed.sort(key=lambda m: m.eval_loss, reverse=True)
        mistake_candidates = [
            m for m in all_analyzed
            if m.eval_loss >= MIN_CRITICAL_EVAL_LOSS
        ]
        top3 = sorted(mistake_candidates[:3], key=lambda m: m.move_index)

        return GameData(
            moves_san=moves_san,
            fens=fens,
            player_color=player_color,
            headers=headers,
            critical_moments=top3,
            all_analyzed=all_analyzed,  # sorted desc by eval_loss
            total_moves=len(moves_san),
        )

    # ------------------------------------------------------------------
    def _analyze_single_move(
        self,
        board: chess.Board,
        move: chess.Move,
        san: str,
        idx: int,
    ) -> Optional[MoveAnalysis]:
        sf = self._sf
        fen_before = board.fen()
        color = "white" if board.turn == chess.WHITE else "black"
        move_number = board.fullmove_number

        try:
            # ---- eval + best move from the position before the move ----
            sf.set_fen_position(fen_before)
            top_moves = sf.get_top_moves(
                max(1, ENGINE_CANDIDATE_LINES),
                verbose=True,
            )
            best_from_multipv = top_moves[0].get("Move") if top_moves else None
            best_uci = best_from_multipv if isinstance(best_from_multipv, str) else sf.get_best_move()
            if not best_uci:
                return None
            eval_before = _cp(sf.get_evaluation())

            best_obj = chess.Move.from_uci(best_uci)
            best_san = board.san(best_obj)
            candidate_lines = _candidate_lines_from_top_moves(board, top_moves)

            # Using eval_before as the best-move baseline keeps dev analysis fast.
            # Set STOCKFISH_EVALUATE_BEST_MOVE=true for a slower, more precise pass.
            if EVALUATE_BEST_MOVE:
                b_best = board.copy()
                b_best.push(best_obj)
                sf.set_fen_position(b_best.fen())
                sf.get_best_move()
                eval_after_best = _cp(sf.get_evaluation())
            else:
                eval_after_best = eval_before

            # ---- eval after player's actual move ----
            b_player = board.copy()
            b_player.push(move)
            sf.set_fen_position(b_player.fen())
            sf.get_best_move()
            eval_after_player = _cp(sf.get_evaluation())

            if not EVALUATE_BEST_MOVE and move == best_obj:
                eval_after_best = eval_after_player

            # ---- eval loss (always positive = player's move was worse) ----
            if color == "white":
                eval_loss = eval_after_best - eval_after_player
            else:
                eval_loss = eval_after_player - eval_after_best
            if eval_loss < 0:
                eval_loss = 0

            pv = candidate_lines[0].line if candidate_lines else [best_san]
            if not pv:
                pv = [best_san]

            return MoveAnalysis(
                move_index=idx,
                move_number=move_number,
                color=color,
                player_move=san,
                best_move=best_san,
                fen_before=fen_before,
                eval_before=eval_before,
                eval_after_player=eval_after_player,
                eval_after_best=eval_after_best,
                eval_loss=eval_loss,
                pv_moves=pv,
                candidate_lines=candidate_lines,
            )
        except Exception as e:
            print(f"[engine] Error on move {san}: {e}")
            return None


# ------------------------------------------------------------------
def _cp(eval_dict: dict) -> int:
    """Normalize Stockfish eval to centipawns from White's perspective."""
    if eval_dict.get("type") == "mate":
        return 10000 if eval_dict.get("value", 1) > 0 else -10000
    return eval_dict.get("value", 0)


def _candidate_lines_from_top_moves(
    board: chess.Board,
    top_moves: list[dict],
) -> list[CandidateLine]:
    candidates: list[CandidateLine] = []
    for row in top_moves:
        move_uci = row.get("Move")
        if not isinstance(move_uci, str):
            continue
        try:
            move = chess.Move.from_uci(move_uci)
            move_san = board.san(move)
        except Exception:
            continue

        pv_uci = str(row.get("PVMoves") or move_uci).split()
        line = _uci_line_to_san(board, pv_uci, max_moves=ENGINE_PV_MAX_MOVES)
        if not line:
            line = [move_san]

        candidates.append(
            CandidateLine(
                move=move_san,
                line=line,
                centipawn=row.get("Centipawn") if isinstance(row.get("Centipawn"), int) else None,
                mate=row.get("Mate") if isinstance(row.get("Mate"), int) else None,
            )
        )
    return candidates


def _uci_line_to_san(board: chess.Board, pv_uci: list[str], max_moves: int) -> list[str]:
    line_board = board.copy()
    san_line: list[str] = []
    for uci in pv_uci[:max_moves]:
        try:
            move = chess.Move.from_uci(uci)
            if move not in line_board.legal_moves:
                break
            san_line.append(line_board.san(move))
            line_board.push(move)
        except Exception:
            break
    return san_line


def _detect_color(headers: dict, player_name: Optional[str]) -> str:
    if player_name:
        white = headers.get("White", "").lower()
        black = headers.get("Black", "").lower()
        name_l = player_name.lower()
        if name_l in white:
            return "white"
        if name_l in black:
            return "black"
    return "white"
