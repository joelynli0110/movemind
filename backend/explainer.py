"""
Claude-powered coach explanations.

Design principle: Engine decides. LLM explains.
All evaluations come from Stockfish; Claude only generates teaching language.

Uses prompt caching on the large system prompt to reduce cost on repeated calls.
"""
import asyncio
import json
import os

import anthropic

from engine import GameData, MoveAnalysis
from position import analyze_position

_client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
_MODEL = "claude-sonnet-4-6"

# ── System prompt (cached) ──────────────────────────────────────────────────
_SYSTEM = """You are MoveMind Coach, an expert chess coach who explains chess mistakes in the style of a patient grandmaster teaching a student.

## Core Philosophy
Do NOT just show the best move. Teach the thought process behind it.

Traditional engine analysis focuses on results ("this move lost 1.5 pawns").
You focus on process:
- Why did the player choose their move? What natural-looking reasoning led to it?
- What was the hidden flaw in that reasoning?
- How does the best move solve the key problem in the position?
- What should the player CHECK FOR next time before making a similar move?

## Teaching levels
- beginner (< 1000 Elo): use everyday language, avoid jargon, explain piece names
- intermediate (1000–1500 Elo): use standard chess terms, give concrete rules of thumb
- advanced (1500–1800 Elo): use precise terminology, discuss subtler strategic concepts

## Output format
Always respond with ONLY valid JSON — no markdown fences, no extra text.
Malformed JSON is a critical failure."""

# ── Mistake explanation prompt ──────────────────────────────────────────────
def _mistake_prompt(m: MoveAnalysis, features, player_elo: int) -> str:
    level = "beginner" if player_elo < 1000 else "intermediate" if player_elo < 1500 else "advanced"
    pv = " ".join(m.pv_moves) if m.pv_moves else "not available"
    tac = ", ".join(features.tactical_motifs) if features.tactical_motifs else "none detected"
    files = ", ".join(features.open_files[:3]) if features.open_files else "none"

    return f"""Analyze this chess mistake and respond with ONLY a JSON object.

CONTEXT
Move {m.move_number} ({m.color} to move) | Player Elo: {player_elo} ({level})
Player's move : {m.player_move}
Engine best   : {m.best_move}
Eval loss     : {m.eval_loss} centipawns
Best line (PV): {pv}

POSITION FEATURES (before the mistake)
Material     : {features.material_balance}
King safety  : {features.king_safety}
Pawn struct  : {features.pawn_structure}
Piece activity: {features.piece_activity}
Tactical motifs: {tac}
Open files   : {files}
FEN          : {m.fen_before}

Respond with this exact JSON structure:
{{
  "mistake_category": "one of: tactical_blindness | king_safety_neglect | wrong_trade | premature_attack | passive_play | pawn_structure_error | missed_tactic | strategic_misunderstanding",
  "mistake_label": "short phrase like 'Missed knight fork' or 'Ignored Bxh7+ sacrifice threat'",
  "why_player_move": "2–3 sentences: first acknowledge why the player's move LOOKS natural, then reveal the hidden problem",
  "why_best_move": "2–3 sentences: explain the KEY IDEA behind the engine's suggestion — compress the PV into one human-understandable concept, not a list of moves",
  "engine_line_idea": "1 sentence summarizing what the best continuation is trying to achieve",
  "how_to_find": [
    "Concrete question or rule (e.g. 'Before moving, ask: does my opponent have a check, capture, or major threat?')",
    "Second rule relevant to this specific mistake",
    "Third rule"
  ],
  "key_lesson": "One memorable sentence the player should internalize from this mistake"
}}"""


# ── Summary + training plan prompt ─────────────────────────────────────────
def _summary_prompt(game_data: GameData, explanations: list[dict], player_elo: int) -> str:
    level = "beginner" if player_elo < 1000 else "intermediate" if player_elo < 1500 else "advanced"
    mistakes_text = "\n".join(
        f"  Mistake {i+1}: [{e.get('mistake_category','?')}] {e.get('mistake_label','?')} — {e.get('key_lesson','')}"
        for i, e in enumerate(explanations)
    )
    opening = game_data.headers.get("Opening", game_data.headers.get("ECO", "Unknown opening"))

    return f"""Based on these chess mistakes, respond with ONLY a JSON object.

PLAYER: {player_elo} Elo ({level})
GAME: {game_data.total_moves} total moves, playing as {game_data.player_color}
OPENING: {opening}

MISTAKES:
{mistakes_text}

Respond with this exact JSON structure:
{{
  "summary": {{
    "biggest_strength": "one thing the player did well or showed promise in",
    "biggest_weakness": "the single most important recurring pattern in their mistakes",
    "key_concept": "the one chess concept most worth studying based on these mistakes",
    "opening_tip": "one specific, actionable opening improvement for next game",
    "accuracy_grade": "one of: A | B | C | D"
  }},
  "training_plan": {{
    "focus_concept": "the #1 concept to work on this week (2–5 words)",
    "focus_explanation": "why this is the priority right now (1–2 sentences)",
    "puzzle_themes": [
      "tactical theme 1 (e.g. 'Bishop sacrifice on h7')",
      "tactical theme 2",
      "tactical theme 3"
    ],
    "pre_move_checklist": [
      "Most important question to ask before EVERY move",
      "Second question",
      "Third question"
    ],
    "weekly_schedule": [
      {{"day": "Day 1", "task": "Specific task (what to study and for how long)"}},
      {{"day": "Day 2", "task": "Specific task"}},
      {{"day": "Day 3", "task": "Specific task"}},
      {{"day": "Day 4", "task": "Rest or light review"}},
      {{"day": "Day 5", "task": "Apply in a real game"}}
    ]
  }}
}}"""


# ── Main class ──────────────────────────────────────────────────────────────
class CoachExplainer:
    def __init__(self, player_elo: int = 1200):
        self.player_elo = player_elo

    async def explain_game(self, game_data: GameData) -> dict:
        if not game_data.critical_moments:
            return _no_mistakes_result(game_data)

        # Explain all 3 critical moments in parallel
        explanations = await asyncio.gather(
            *[self._explain_mistake(m) for m in game_data.critical_moments]
        )

        summary_and_plan = await self._generate_summary(game_data, list(explanations))

        return {
            "game": {
                "moves_san": game_data.moves_san,
                "fens": game_data.fens,
                "player_color": game_data.player_color,
                "headers": game_data.headers,
                "total_moves": game_data.total_moves,
            },
            "critical_moments": [
                {
                    "move_index": m.move_index,
                    "move_number": m.move_number,
                    "color": m.color,
                    "fen_before": m.fen_before,
                    "player_move": m.player_move,
                    "best_move": m.best_move,
                    "eval_loss": m.eval_loss,
                    "pv_moves": m.pv_moves,
                    "explanation": exp,
                    "position_features": vars(analyze_position(m.fen_before)),
                }
                for m, exp in zip(game_data.critical_moments, explanations)
            ],
            "game_summary": summary_and_plan.get("summary", {}),
            "training_plan": summary_and_plan.get("training_plan", {}),
        }

    async def _explain_mistake(self, m: MoveAnalysis) -> dict:
        features = analyze_position(m.fen_before)
        prompt = _mistake_prompt(m, features, self.player_elo)
        try:
            resp = await _client.messages.create(
                model=_MODEL,
                max_tokens=1024,
                system=[{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": prompt}],
            )
            return _parse_json(resp.content[0].text)
        except Exception as e:
            print(f"[explainer] Claude error for move {m.player_move}: {e}")
            return _fallback_explanation(m)

    async def _generate_summary(self, game_data: GameData, explanations: list[dict]) -> dict:
        prompt = _summary_prompt(game_data, explanations, self.player_elo)
        try:
            resp = await _client.messages.create(
                model=_MODEL,
                max_tokens=1024,
                system=[{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": prompt}],
            )
            return _parse_json(resp.content[0].text)
        except Exception as e:
            print(f"[explainer] Claude summary error: {e}")
            return _fallback_summary()


# ── Helpers ─────────────────────────────────────────────────────────────────
def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1].lstrip("json").strip() if len(parts) > 1 else text
    return json.loads(text)


def _fallback_explanation(m: MoveAnalysis) -> dict:
    return {
        "mistake_category": "tactical_blindness",
        "mistake_label": f"Move {m.move_number}: suboptimal choice",
        "why_player_move": (
            f"{m.player_move} is a natural-looking move, but it loses about "
            f"{m.eval_loss // 100:.1f} pawn{'s' if m.eval_loss >= 200 else ''} of advantage."
        ),
        "why_best_move": (
            f"{m.best_move} is stronger because it better addresses the key tension in the position."
        ),
        "engine_line_idea": "The best continuation improves piece coordination and controls key squares.",
        "how_to_find": [
            "Before moving, check: does my opponent have a check, capture, or major threat?",
            "Ask: which of my pieces is least active? Can I improve it?",
            "Consider: does my move create any new weaknesses?",
        ],
        "key_lesson": "Always check your opponent's forcing moves before executing your own plan.",
    }


def _fallback_summary() -> dict:
    return {
        "summary": {
            "biggest_strength": "You fought through the game and completed all phases",
            "biggest_weakness": "Missing opponent's forcing moves (checks, captures, threats)",
            "key_concept": "Candidate move thinking — always check opponent threats first",
            "opening_tip": "Review the first 10 moves of your opening and understand each move's purpose",
            "accuracy_grade": "C",
        },
        "training_plan": {
            "focus_concept": "Checks, Captures, Threats",
            "focus_explanation": (
                "Before every move, scan for your opponent's forcing options. "
                "This simple habit prevents most tactical blunders."
            ),
            "puzzle_themes": ["Forks", "Pins", "Back-rank checkmates"],
            "pre_move_checklist": [
                "Does my opponent have a check?",
                "Does my opponent have a capture?",
                "Does my opponent have a threat I must address?",
            ],
            "weekly_schedule": [
                {"day": "Day 1", "task": "Solve 10 fork puzzles (15 min)"},
                {"day": "Day 2", "task": "Re-play this game and pause at each mistake position"},
                {"day": "Day 3", "task": "Solve 10 pin + discovered attack puzzles (15 min)"},
                {"day": "Day 4", "task": "Light review — read through your checklist"},
                {"day": "Day 5", "task": "Play a 15+10 game and use the pre-move checklist every move"},
            ],
        },
    }


def _no_mistakes_result(game_data: GameData) -> dict:
    return {
        "game": {
            "moves_san": game_data.moves_san,
            "fens": game_data.fens,
            "player_color": game_data.player_color,
            "headers": game_data.headers,
            "total_moves": game_data.total_moves,
        },
        "critical_moments": [],
        "game_summary": {
            "biggest_strength": "Excellent accuracy throughout — no major mistakes detected!",
            "biggest_weakness": "No significant mistakes found in this game",
            "key_concept": "Keep refining strategic understanding and calculation depth",
            "opening_tip": "Your opening play was solid",
            "accuracy_grade": "A",
        },
        "training_plan": {
            "focus_concept": "Advanced Strategy",
            "focus_explanation": "You played very accurately. Focus on refining long-term strategic planning.",
            "puzzle_themes": ["Complex tactics", "Endgame technique", "Positional sacrifices"],
            "pre_move_checklist": [
                "What is my opponent's best response to my move?",
                "Can I improve my worst-placed piece?",
                "Is there a pawn break I should consider?",
            ],
            "weekly_schedule": [
                {"day": "Day 1", "task": "Study an endgame concept (rook endgames, 20 min)"},
                {"day": "Day 2", "task": "Solve advanced tactical puzzles (20 min)"},
                {"day": "Day 3", "task": "Play a training game with focus on strategic planning"},
                {"day": "Day 4", "task": "Review a master game in your opening"},
                {"day": "Day 5", "task": "Analyze your game from Day 3"},
            ],
        },
    }
