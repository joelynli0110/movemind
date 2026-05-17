"""
Smoke-test for the LLM coaching pipeline.
Works with both Anthropic and Ollama — reads LLM_PROVIDER from .env.

Run from the backend directory:
    python3 test_llm.py
"""
import asyncio
import os
import sys

from dotenv import load_dotenv
load_dotenv()

_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic").lower()
_ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
_OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
_OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")


# ── Provider checks ───────────────────────────────────────────────────────────

def check_provider_config():
    print(f"[1] LLM_PROVIDER = {_PROVIDER!r}")

    if _PROVIDER == "anthropic":
        if not _ANTHROPIC_KEY or _ANTHROPIC_KEY.startswith("your_"):
            print("    ERROR: ANTHROPIC_API_KEY is not set.")
            print("    Set it in .env:  ANTHROPIC_API_KEY=sk-ant-...")
            sys.exit(1)
        print(f"    OK: key starts with {_ANTHROPIC_KEY[:12]}...")

    elif _PROVIDER == "ollama":
        print(f"    Base URL : {_OLLAMA_BASE}")
        print(f"    Model    : {_OLLAMA_MODEL}")

    else:
        print(f"    ERROR: Unknown LLM_PROVIDER {_PROVIDER!r}. Use 'anthropic' or 'ollama'.")
        sys.exit(1)


async def check_provider_connectivity():
    """Ping the provider to confirm it's reachable before running heavier tests."""
    print(f"\n[2] Connectivity check for {_PROVIDER}...")

    if _PROVIDER == "anthropic":
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=_ANTHROPIC_KEY)
        try:
            resp = await client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=16,
                messages=[{"role": "user", "content": "Reply with: OK"}],
            )
            print(f"    Response: {resp.content[0].text.strip()!r}")
            print("    OK")
        except Exception as e:
            print(f"    ERROR: {e}")
            sys.exit(1)

    elif _PROVIDER == "ollama":
        import httpx
        # Check /api/tags to confirm Ollama is running and the model is pulled
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{_OLLAMA_BASE}/api/tags")
                resp.raise_for_status()
                tags = resp.json()
                available = [m["name"] for m in tags.get("models", [])]
                print(f"    Ollama running. Available models: {available}")

                # Check if the configured model is present
                # Model names may include tags like "qwen3:8b" or just "qwen3"
                match = any(
                    _OLLAMA_MODEL == m or _OLLAMA_MODEL.split(":")[0] == m.split(":")[0]
                    for m in available
                )
                if not match:
                    print(f"    WARNING: model {_OLLAMA_MODEL!r} not found in Ollama.")
                    print(f"    Pull it with:  ollama pull {_OLLAMA_MODEL}")
                    print("    Continuing anyway — the next test will confirm if it works.")
                else:
                    print(f"    Model {_OLLAMA_MODEL!r} is available.")
                print("    OK")
        except httpx.ConnectError:
            print(f"    ERROR: Cannot reach Ollama at {_OLLAMA_BASE}")
            print("    Make sure Ollama is running: ollama serve")
            sys.exit(1)
        except Exception as e:
            print(f"    ERROR: {e}")
            sys.exit(1)


# ── Position features (no LLM needed) ────────────────────────────────────────

async def test_position_features():
    print("\n[3] Position feature extraction (engine-only, no LLM)...")
    try:
        from position import analyze_position
        fen = "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2N2N2/PPPP1PPP/R1BQK2R w KQkq - 4 4"
        f = analyze_position(fen)
        print(f"    Material  : {f.material_balance}")
        print(f"    King      : {f.king_safety}")
        print(f"    Pawns     : {f.pawn_structure}")
        print(f"    Motifs    : {f.tactical_motifs}")
        print("    OK")
    except Exception as e:
        print(f"    ERROR: {e}")
        sys.exit(1)


# ── Raw LLM call via abstraction ──────────────────────────────────────────────

async def test_raw_llm_call():
    print(f"\n[4] Raw call through llm.call_llm ({_PROVIDER})...")
    from llm import call_llm
    try:
        text = await call_llm(
            system="You are a test assistant. Follow instructions exactly.",
            user_prompt='Reply with exactly this JSON and nothing else: {"status": "MOVEMIND_OK"}',
            max_tokens=256,  # thinking models need budget for reasoning before the answer
        )
        print(f"    Raw response: {text.strip()!r}")
        # Loose check — just confirm we got something back
        assert "MOVEMIND_OK" in text or "status" in text, f"Unexpected: {text}"
        print("    OK")
    except Exception as e:
        print(f"    ERROR: {e}")
        sys.exit(1)


# ── Single mistake explanation ────────────────────────────────────────────────

async def test_explain_mistake():
    print(f"\n[5] Explain a single chess mistake ({_PROVIDER})...")
    from engine import MoveAnalysis
    from explainer import CoachExplainer

    mock = MoveAnalysis(
        move_index=11,
        move_number=12,
        color="black",
        player_move="Nc6",
        best_move="h6",
        fen_before="r1bq1rk1/ppp2ppp/2n2n2/2b1p1B1/2B1P3/2N2N2/PPPP1PPP/R2QK2R b KQ - 0 8",
        eval_before=30,
        eval_after_player=180,
        eval_after_best=20,
        eval_loss=160,
        pv_moves=["h6", "Bh4", "g5", "Bg3"],
    )

    try:
        explainer = CoachExplainer(player_elo=1200)
        result = await explainer._explain_mistake(mock)

        if result is None:
            print("    ERROR: explanation returned None (LLM call failed)")
            sys.exit(1)

        print(f"    Category  : {result.get('mistake_category')}")
        print(f"    Label     : {result.get('mistake_label')}")
        print(f"    Why wrong : {str(result.get('why_player_move', ''))[:80]}...")
        print(f"    Checklist : {result.get('how_to_find', [])}")
        print(f"    Key lesson: {str(result.get('key_lesson', ''))[:80]}")
        print("    OK")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"    ERROR: {e}")
        sys.exit(1)


# ── Full pipeline with mock GameData ─────────────────────────────────────────

async def test_full_pipeline():
    print(f"\n[6] Full CoachExplainer pipeline ({_PROVIDER})...")
    from engine import GameData, MoveAnalysis
    from explainer import CoachExplainer

    mock_game = GameData(
        moves_san=["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5", "b4", "Bxb4",
                   "c3", "Ba5", "d4", "exd4", "O-O"],
        fens=["rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"] * 14,
        player_color="white",
        headers={"White": "You", "Black": "Opponent", "Result": "1-0", "Opening": "Evans Gambit"},
        critical_moments=[
            MoveAnalysis(
                move_index=6,
                move_number=4,
                color="white",
                player_move="b4",
                best_move="d3",
                fen_before="r1bqk1nr/pppp1ppp/2n5/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 2 4",
                eval_before=30,
                eval_after_player=-40,
                eval_after_best=60,
                eval_loss=100,
                pv_moves=["d3", "Nf6", "Nc3"],
            )
        ],
        total_moves=13,
    )

    try:
        explainer = CoachExplainer(player_elo=1300)
        result = await explainer.explain_game(mock_game)

        moments = result.get("critical_moments", [])
        summary = result.get("game_summary")
        plan = result.get("training_plan")
        llm_ok = result.get("llm_available")

        print(f"    llm_available  : {llm_ok}")
        print(f"    Moments returned: {len(moments)}")

        if not moments:
            print("    ERROR: no critical moments returned")
            sys.exit(1)

        exp = moments[0].get("explanation")
        if exp is None:
            print("    ERROR: explanation is None — LLM call failed (check logs above for details)")
            sys.exit(1)

        print(f"    Mistake label  : {exp.get('mistake_label')}")
        print(f"    Key lesson     : {str(exp.get('key_lesson',''))[:80]}")

        if summary is None:
            print("    ERROR: game_summary is None — summary LLM call failed")
            sys.exit(1)

        print(f"    Grade          : {summary.get('accuracy_grade')}")
        print(f"    Focus concept  : {plan.get('focus_concept') if plan else 'N/A'}")
        print("    OK")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"    ERROR: {e}")
        sys.exit(1)


# ── Runner ────────────────────────────────────────────────────────────────────

async def main():
    print("=" * 55)
    print(f"  MoveMind — LLM Tests  (provider: {_PROVIDER})")
    print("=" * 55)
    check_provider_config()
    await check_provider_connectivity()
    await test_position_features()
    await test_raw_llm_call()
    await test_explain_mistake()
    await test_full_pipeline()
    print("\nAll LLM tests passed.")


if __name__ == "__main__":
    asyncio.run(main())
