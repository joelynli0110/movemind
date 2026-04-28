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

STOCKFISH_PATH = os.getenv("STOCKFISH_PATH", "stockfish")
QUICK_DEPTH = 12
CENTIPAWN_THRESHOLD = 80  # Minimum eval loss to flag as a mistake


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
    pv_moves: list[str] = field(default_factory=list)  # SAN list of best continuation


@dataclass
class GameData:
    moves_san: list[str]
    fens: list[str]          # fens[0] = start, fens[i] = after moves_san[i-1]
    player_color: str
    headers: dict
    critical_moments: list[MoveAnalysis]
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
        candidates: list[MoveAnalysis] = []

        for idx, move in enumerate(game.mainline_moves()):
            san = board.san(move)
            moves_san.append(san)

            is_player = (
                (board.turn == chess.WHITE and player_color == "white") or
                (board.turn == chess.BLACK and player_color == "black")
            )

            if self._sf and is_player:
                analysis = self._analyze_single_move(board, move, san, idx)
                if analysis and analysis.eval_loss >= CENTIPAWN_THRESHOLD:
                    candidates.append(analysis)

            board.push(move)
            fens.append(board.fen())

        # Top 3 by eval loss, then re-sort chronologically
        candidates.sort(key=lambda m: m.eval_loss, reverse=True)
        top3 = sorted(candidates[:3], key=lambda m: m.move_index)

        return GameData(
            moves_san=moves_san,
            fens=fens,
            player_color=player_color,
            headers=headers,
            critical_moments=top3,
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
            best_uci = sf.get_best_move()
            if not best_uci:
                return None
            eval_before = _cp(sf.get_evaluation())

            best_obj = chess.Move.from_uci(best_uci)
            best_san = board.san(best_obj)

            # ---- eval after best move ----
            b_best = board.copy()
            b_best.push(best_obj)
            sf.set_fen_position(b_best.fen())
            sf.get_best_move()
            eval_after_best = _cp(sf.get_evaluation())

            # ---- eval after player's actual move ----
            b_player = board.copy()
            b_player.push(move)
            sf.set_fen_position(b_player.fen())
            sf.get_best_move()
            eval_after_player = _cp(sf.get_evaluation())

            # ---- eval loss (always positive = player's move was worse) ----
            if color == "white":
                eval_loss = eval_after_best - eval_after_player
            else:
                eval_loss = eval_after_player - eval_after_best
            if eval_loss < 0:
                eval_loss = 0

            # ---- collect a short PV (3 moves) for context ----
            pv = [best_san]
            b_pv = board.copy()
            b_pv.push(best_obj)
            for _ in range(2):
                sf.set_fen_position(b_pv.fen())
                nxt = sf.get_best_move()
                if not nxt:
                    break
                try:
                    nxt_obj = chess.Move.from_uci(nxt)
                    pv.append(b_pv.san(nxt_obj))
                    b_pv.push(nxt_obj)
                except Exception:
                    break

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
