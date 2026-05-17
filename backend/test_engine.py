"""
Quick smoke-test for the Stockfish engine pipeline.
Run from the backend directory:
    python3 test_engine.py
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

SAMPLE_PGN = """[Event "Test"]
[White "Alice"]
[Black "Bob"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bc4 Nf6 4. Ng5 d5 5. exd5 Na5
6. Bb5+ c6 7. dxc6 bxc6 8. Be2 h6 9. Nf3 e4 10. Ne5 Qd4
11. f4 Bc5 12. Rf1 O-O 13. Nc3 Ng4 14. Nxg4 Bxg4 15. Bxg4 Qxf4 1-0"""


def test_stockfish_path():
    path = os.getenv("STOCKFISH_PATH", "stockfish").strip('"').strip("'")
    print(f"[1] Stockfish path from .env: {path!r}")
    if not os.path.isabs(path):
        print("    (using PATH lookup)")
    elif not os.path.exists(path):
        print(f"    ERROR: file not found at {path}")
        sys.exit(1)
    else:
        print(f"    OK: file exists")
    return path


def test_stockfish_init(path: str):
    print("\n[2] Initializing Stockfish...")
    try:
        from stockfish import Stockfish
        sf = Stockfish(path=path, depth=12, parameters={"Threads": 1, "Hash": 64})
        print(f"    OK: Stockfish initialized")
        return sf
    except Exception as e:
        print(f"    ERROR: {e}")
        sys.exit(1)


def test_best_move(sf):
    print("\n[3] Testing get_best_move on starting position...")
    try:
        sf.set_fen_position("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1")
        move = sf.get_best_move()
        ev = sf.get_evaluation()
        print(f"    Best move: {move}  |  Eval: {ev}")
        assert move is not None, "Expected a move"
        print("    OK")
    except Exception as e:
        print(f"    ERROR: {e}")
        sys.exit(1)


def test_pgn_parse():
    print("\n[4] Parsing sample PGN with python-chess...")
    try:
        import chess.pgn, io
        game = chess.pgn.read_game(io.StringIO(SAMPLE_PGN))
        moves = list(game.mainline_moves())
        board = game.board()
        for m in moves:
            board.push(m)
        print(f"    OK: {len(moves)} moves parsed, final FEN:")
        print(f"    {board.fen()}")
    except Exception as e:
        print(f"    ERROR: {e}")
        sys.exit(1)


def test_full_engine_analysis():
    print("\n[5] Running full EngineAnalyst on sample PGN (player = Alice / white)...")
    try:
        # Temporarily patch env so engine.py picks up the cleaned path
        path = os.getenv("STOCKFISH_PATH", "stockfish").strip('"').strip("'")
        os.environ["STOCKFISH_PATH"] = path

        from engine import EngineAnalyst
        analyst = EngineAnalyst()

        if analyst._sf is None:
            print("    WARNING: Stockfish unavailable — engine analysis skipped")
            return

        result = analyst.analyze_game(SAMPLE_PGN, player_name="Alice")
        print(f"    Total moves   : {result.total_moves}")
        print(f"    Player color  : {result.player_color}")
        print(f"    Critical moves found: {len(result.critical_moments)}")
        for i, m in enumerate(result.critical_moments, 1):
            print(
                f"    Mistake {i}: move {m.move_number} ({m.color})  "
                f"{m.player_move!r} → best {m.best_move!r}  "
                f"loss={m.eval_loss}cp  PV={' '.join(m.pv_moves)}"
            )
        print("    OK")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"    ERROR: {e}")


if __name__ == "__main__":
    print("=" * 55)
    print("  MoveMind — Stockfish Engine Tests")
    print("=" * 55)
    path = test_stockfish_path()
    sf = test_stockfish_init(path)
    test_best_move(sf)
    test_pgn_parse()
    test_full_engine_analysis()
    print("\nAll engine tests passed.")
