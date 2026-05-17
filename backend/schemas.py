from pydantic import BaseModel
from typing import Optional


class AnalyzeTextRequest(BaseModel):
    pgn_text: str
    player_name: Optional[str] = None
    player_elo: int = 1200
    language: str = "en"
