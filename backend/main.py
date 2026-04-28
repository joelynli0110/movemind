import uuid
from typing import Optional

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from engine import EngineAnalyst
from explainer import CoachExplainer
from schemas import AnalyzeTextRequest

app = FastAPI(title="MoveMind AI Chess Coach API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store — use Redis/Postgres in production
_store: dict[str, dict] = {}


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.post("/api/analyze")
async def analyze_pgn_file(
    background_tasks: BackgroundTasks,
    pgn: UploadFile = File(...),
    player_name: Optional[str] = Form(None),
    player_elo: int = Form(1200),
):
    """Accept a PGN file upload and start background analysis."""
    raw = await pgn.read()
    pgn_text = raw.decode("utf-8", errors="replace")
    game_id = str(uuid.uuid4())
    _store[game_id] = {"status": "processing"}
    background_tasks.add_task(_run_analysis, game_id, pgn_text, player_name, player_elo)
    return {"game_id": game_id, "status": "processing"}


@app.post("/api/analyze/text")
async def analyze_pgn_text(
    background_tasks: BackgroundTasks,
    body: AnalyzeTextRequest,
):
    """Accept a PGN as plain text (useful for paste-in flows)."""
    game_id = str(uuid.uuid4())
    _store[game_id] = {"status": "processing"}
    background_tasks.add_task(
        _run_analysis, game_id, body.pgn_text, body.player_name, body.player_elo
    )
    return {"game_id": game_id, "status": "processing"}


@app.get("/api/game/{game_id}")
async def get_game(game_id: str):
    """Poll this endpoint until status == 'complete' or 'error'."""
    if game_id not in _store:
        raise HTTPException(status_code=404, detail="Game not found")
    return _store[game_id]


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# ── Background task ──────────────────────────────────────────────────────────

async def _run_analysis(
    game_id: str,
    pgn_text: str,
    player_name: Optional[str],
    player_elo: int,
):
    try:
        analyst = EngineAnalyst()
        game_data = analyst.analyze_game(pgn_text, player_name)

        explainer = CoachExplainer(player_elo=player_elo)
        result = await explainer.explain_game(game_data)

        _store[game_id] = {"status": "complete", "result": result}
    except Exception as exc:
        import traceback
        traceback.print_exc()
        _store[game_id] = {"status": "error", "error": str(exc)}
