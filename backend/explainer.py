"""
Coach explanation pipeline.

Engine decides. The LLM explains. When Chinese is requested, the app first
generates stable English JSON, then uses the configured machine translator for
the user-facing values.
"""
import os

from engine import GameData, MoveAnalysis
from llm import call_llm, is_llm_available, parse_llm_json
from position import analyze_position
from translator import translate_json_values

LLM_EXPLANATION_MAX_TOKENS = int(os.getenv("LLM_EXPLANATION_MAX_TOKENS", "900"))
LLM_SUMMARY_MAX_TOKENS = int(os.getenv("LLM_SUMMARY_MAX_TOKENS", "640"))

_EXPLANATION_TRANSLATABLE_FIELDS = (
    "mistake_label",
    "engine_layer",
    "tactical_layer",
    "strategic_layer",
    "human_layer",
    "engine_line_idea",
    "coach_question",
    "how_to_find",
    "key_lesson",
)


def _normalize_language(language: str | None) -> str:
    return "zh" if language == "zh" else "en"


def _position_features_dict(fen: str) -> dict:
    return vars(analyze_position(fen))


_SYSTEM = """You are MoveMind Coach, an expert chess coach who explains chess mistakes in the style of a patient grandmaster teaching a student.

## Core Philosophy
Do NOT just show the best move. Teach the thought process behind it.

Traditional engine analysis focuses on results ("this move lost 1.5 pawns").
You focus on process:
- Why did the player choose their move? What natural-looking reasoning led to it?
- What was the hidden flaw in that reasoning?
- How does the best move solve the key problem in the position?
- What should the player check for next time before making a similar move?

## Teaching levels
- beginner (< 1000 Elo): use everyday language, avoid jargon, explain piece names
- intermediate (1000-1500 Elo): use standard chess terms, give concrete rules of thumb
- advanced (1500-1800 Elo): use precise terminology, discuss subtler strategic concepts

## Output format
Always respond with ONLY valid JSON. No markdown fences, no extra text.
Malformed JSON is a critical failure.
Write every user-facing JSON value in English."""


def _mistake_prompt(m: MoveAnalysis, features, player_elo: int) -> str:
    level = "beginner" if player_elo < 1000 else "intermediate" if player_elo < 1500 else "advanced"
    pv = " ".join(m.pv_moves) if m.pv_moves else "not available"
    candidates = "\n".join(
        f"  {i + 1}. {c.move}: {' '.join(c.line) if c.line else c.move}"
        f" | eval={_format_candidate_eval(c.centipawn, c.mate)}"
        for i, c in enumerate(m.candidate_lines[:3])
    ) or "  not available"
    tac = ", ".join(features.tactical_motifs) if features.tactical_motifs else "none detected"
    files = ", ".join(features.open_files[:3]) if features.open_files else "none"

    return f"""Analyze this chess {m.severity} and respond with ONLY a JSON object.

CONTEXT
Move {m.move_number} ({m.color} to move) | Player Elo: {player_elo} ({level})
Severity      : {m.severity} ({m.eval_loss} centipawns lost)
Player's move : {m.player_move}
Engine best   : {m.best_move}
Best line (PV): {pv}
Candidate lines:
{candidates}

POSITION FEATURES (before the mistake)
Material      : {features.material_balance}
King safety   : {features.king_safety}
Pawn structure: {features.pawn_structure}
Piece activity: {features.piece_activity}
Tactical motifs: {tac}
Open files    : {files}
FEN           : {m.fen_before}

Respond with this exact JSON structure:
{{
  "mistake_category": "one of: tactical_blindness | king_safety_neglect | wrong_trade | premature_attack | passive_play | pawn_structure_error | missed_tactic | strategic_misunderstanding",
  "mistake_label": "short phrase like 'Missed knight fork' or 'Ignored Bxh7+ sacrifice threat'",
  "engine_layer": {{
    "eval_summary": "1 sentence explaining the eval loss and best move in human terms",
    "best_line": "the engine line as SAN text, copied from the PV when useful",
    "candidate_summary": "1 sentence comparing the top candidates without overloading the user"
  }},
  "tactical_layer": {{
    "motif": "the concrete tactical theme, or 'No forcing tactic detected'",
    "explanation": "1-2 sentences about checks, captures, threats, pins, forks, or other forcing details"
  }},
  "strategic_layer": {{
    "concept": "the long-term positional concept involved",
    "explanation": "1-2 sentences about king safety, pawn structure, open files, weak squares, piece activity, or trades"
  }},
  "human_layer": {{
    "likely_thought": "1 sentence explaining why the player's move looked natural to a human",
    "correction": "1-2 sentences naming the thinking habit to fix next time"
  }},
  "engine_line_idea": "1 sentence summarizing what the best continuation is trying to achieve",
  "coach_question": "one Socratic question the coach should ask before revealing the answer",
  "how_to_find": [
    "Concrete question or rule the player should ask before similar moves",
    "Second rule relevant to this specific mistake",
    "Third rule"
  ],
  "key_lesson": "One memorable sentence the player should internalize"
}}"""


def _format_candidate_eval(centipawn: int | None, mate: int | None) -> str:
    if mate is not None:
        return f"mate {mate}"
    if centipawn is not None:
        return f"{centipawn / 100:+.2f}"
    return "n/a"


def _summary_prompt(game_data: GameData, explanations: list[dict], player_elo: int) -> str:
    level = "beginner" if player_elo < 1000 else "intermediate" if player_elo < 1500 else "advanced"
    mistakes_text = "\n".join(
        f"  Mistake {i + 1}: [{e.get('mistake_category', '?')}] "
        f"{e.get('mistake_label', '?')} - {e.get('key_lesson', '')}"
        for i, e in enumerate(explanations)
        if e is not None
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
    "key_concept": "the one chess concept most worth studying",
    "opening_tip": "one specific, actionable opening improvement for next game",
    "accuracy_grade": "one of: A | B | C | D"
  }},
  "training_plan": {{
    "focus_concept": "the #1 concept to work on this week (2-5 words)",
    "focus_explanation": "why this is the priority right now (1-2 sentences)",
    "puzzle_themes": [
      "tactical theme 1",
      "tactical theme 2",
      "tactical theme 3"
    ],
    "pre_move_checklist": [
      "Most important question to ask before EVERY move",
      "Second question",
      "Third question"
    ],
    "weekly_schedule": [
      {{"day": "Day 1", "task": "Specific task"}},
      {{"day": "Day 2", "task": "Specific task"}},
      {{"day": "Day 3", "task": "Specific task"}},
      {{"day": "Day 4", "task": "Rest or light review"}},
      {{"day": "Day 5", "task": "Apply in a real game"}}
    ]
  }}
}}"""


class CoachExplainer:
    def __init__(self, player_elo: int = 1200, language: str = "en"):
        self.player_elo = player_elo
        self.language = _normalize_language(language)
        self._llm_available = is_llm_available()

    async def explain_game(self, game_data: GameData) -> dict:
        def _serialize_move(m: MoveAnalysis) -> dict:
            return {
                "move_index": m.move_index,
                "move_number": m.move_number,
                "color": m.color,
                "player_move": m.player_move,
                "best_move": m.best_move,
                "eval_loss": m.eval_loss,
                "severity": m.severity,
                "eval_before": m.eval_before,
                "eval_after_player": m.eval_after_player,
                "eval_after_best": m.eval_after_best,
                "pv_moves": m.pv_moves,
                "candidate_lines": [
                    {
                        "move": c.move,
                        "line": c.line,
                        "centipawn": c.centipawn,
                        "mate": c.mate,
                    }
                    for c in m.candidate_lines
                ],
            }

        base = {
            "language": self.language,
            "game": {
                "moves_san": game_data.moves_san,
                "fens": game_data.fens,
                "player_color": game_data.player_color,
                "headers": game_data.headers,
                "total_moves": game_data.total_moves,
            },
            "engine_analysis": [_serialize_move(m) for m in game_data.all_analyzed],
            "llm_available": self._llm_available,
        }

        if not game_data.critical_moments:
            return {**base, "critical_moments": [], "game_summary": None, "training_plan": None}

        if not self._llm_available:
            critical_moments = []
            for m in game_data.critical_moments:
                critical_moments.append(
                    {
                        **_serialize_move(m),
                        "fen_before": m.fen_before,
                        "explanation": None,
                        "position_features": await self._position_features(m.fen_before),
                    }
                )
            return {
                **base,
                "critical_moments": critical_moments,
                "game_summary": None,
                "training_plan": {"puzzles": self._build_training_puzzles(game_data, [])},
            }

        english_explanations = []
        for moment in game_data.critical_moments:
            english_explanations.append(await self._explain_mistake(moment))

        summary_data = await self._generate_summary(game_data, english_explanations)

        output_explanations = []
        for exp in english_explanations:
            output_explanations.append(await self._translate_explanation(exp) if exp else None)
        output_summary = await self._translate_summary(summary_data) if summary_data else None
        puzzles = self._build_training_puzzles(game_data, output_explanations)

        critical_moments = []
        for m, exp in zip(game_data.critical_moments, output_explanations):
            critical_moments.append(
                {
                    **_serialize_move(m),
                    "fen_before": m.fen_before,
                    "explanation": exp,
                    "position_features": await self._position_features(m.fen_before),
                }
            )

        return {
            **base,
            "critical_moments": critical_moments,
            "game_summary": output_summary.get("summary") if output_summary else None,
            "training_plan": self._merge_training_puzzles(
                output_summary.get("training_plan") if output_summary else None,
                puzzles,
            ),
        }

    async def _explain_mistake(self, m: MoveAnalysis) -> dict | None:
        features = analyze_position(m.fen_before)
        prompt = _mistake_prompt(m, features, self.player_elo)
        try:
            text = await call_llm(_SYSTEM, prompt, max_tokens=LLM_EXPLANATION_MAX_TOKENS)
            return _normalize_explanation(parse_llm_json(text), m)
        except Exception as e:
            print(f"[explainer] LLM error for move {m.player_move}: {type(e).__name__}: {e}")
            return None

    async def _generate_summary(self, game_data: GameData, explanations: list) -> dict | None:
        valid = [e for e in explanations if e is not None]
        if not valid:
            return None
        prompt = _summary_prompt(game_data, valid, self.player_elo)
        try:
            text = await call_llm(_SYSTEM, prompt, max_tokens=LLM_SUMMARY_MAX_TOKENS)
            return parse_llm_json(text)
        except Exception as e:
            print(f"[explainer] LLM summary error: {type(e).__name__}: {e}")
            return None

    async def _position_features(self, fen: str) -> dict:
        features = _position_features_dict(fen)
        if self.language != "zh":
            return features
        try:
            translated = await translate_json_values(features, "zh")
            return translated if isinstance(translated, dict) else features
        except Exception as e:
            print(f"[explainer] translation error for position features: {type(e).__name__}: {e}")
            return features

    async def _translate_explanation(self, explanation: dict) -> dict:
        if self.language != "zh":
            return explanation
        payload = {
            key: explanation[key]
            for key in _EXPLANATION_TRANSLATABLE_FIELDS
            if key in explanation
        }
        try:
            translated = await translate_json_values(payload, "zh")
            if isinstance(translated, dict):
                return {**explanation, **translated}
        except Exception as e:
            print(f"[explainer] translation error for explanation: {type(e).__name__}: {e}")
        return explanation

    async def _translate_summary(self, summary_data: dict) -> dict:
        if self.language != "zh":
            return summary_data
        payload = {
            "summary": {
                key: value
                for key, value in summary_data.get("summary", {}).items()
                if key != "accuracy_grade"
            },
            "training_plan": summary_data.get("training_plan", {}),
        }
        try:
            translated = await translate_json_values(payload, "zh")
            if isinstance(translated, dict):
                merged = dict(summary_data)
                merged_summary = dict(summary_data.get("summary", {}))
                merged_summary.update(translated.get("summary", {}))
                merged["summary"] = merged_summary
                if "training_plan" in translated:
                    merged["training_plan"] = translated["training_plan"]
                return merged
        except Exception as e:
            print(f"[explainer] translation error for summary: {type(e).__name__}: {e}")
        return summary_data

    def _build_training_puzzles(self, game_data: GameData, explanations: list[dict | None]) -> list[dict]:
        puzzles = []
        for index, moment in enumerate(game_data.critical_moments):
            explanation = explanations[index] if index < len(explanations) else None
            label = explanation.get("mistake_label") if explanation else f"Find {moment.best_move}"
            category = explanation.get("mistake_category") if explanation else moment.severity
            coach_question = explanation.get("coach_question") if explanation else None
            puzzles.append(
                {
                    "id": f"{moment.move_index}-{moment.best_move}",
                    "fen": moment.fen_before,
                    "move_number": moment.move_number,
                    "side_to_move": moment.color,
                    "prompt": coach_question or "Find the engine move and explain what it fixes.",
                    "solution": moment.best_move,
                    "solution_line": moment.pv_moves,
                    "theme": category,
                    "source_mistake": moment.player_move,
                    "label": label,
                }
            )
        return puzzles

    def _merge_training_puzzles(self, training_plan: dict | None, puzzles: list[dict]) -> dict | None:
        if training_plan is None and not puzzles:
            return None
        merged = dict(training_plan or {})
        merged["puzzles"] = puzzles
        return merged


def _normalize_explanation(data: dict, m: MoveAnalysis) -> dict:
    """Keep the frontend stable even if an LLM returns an older shape."""
    why_player = data.get("why_player_move", "")
    why_best = data.get("why_best_move", "")
    engine_line = " ".join(m.pv_moves) if m.pv_moves else m.best_move

    data.setdefault("mistake_category", "strategic_misunderstanding")
    data.setdefault("mistake_label", f"Better was {m.best_move}")
    engine_layer = _ensure_dict(data, "engine_layer")
    engine_layer.setdefault(
        "eval_summary",
        f"{m.player_move} lost about {m.eval_loss / 100:.1f} pawns; Stockfish preferred {m.best_move}.",
    )
    engine_layer.setdefault("best_line", engine_line)
    engine_layer.setdefault(
        "candidate_summary",
        why_best or "The top engine candidate handles the position's most urgent problem.",
    )

    tactical_layer = _ensure_dict(data, "tactical_layer")
    tactical_layer.setdefault("motif", "Review forcing moves")
    tactical_layer.setdefault(
        "explanation",
        why_player or "Check whether either side has checks, captures, or direct threats.",
    )

    strategic_layer = _ensure_dict(data, "strategic_layer")
    strategic_layer.setdefault("concept", "Position priorities")
    strategic_layer.setdefault(
        "explanation",
        why_best or "The best move improves the position before pursuing a less urgent plan.",
    )

    human_layer = _ensure_dict(data, "human_layer")
    human_layer.setdefault(
        "likely_thought",
        why_player or f"{m.player_move} probably looked natural during the game.",
    )
    human_layer.setdefault(
        "correction",
        "Pause before natural moves and identify the opponent's most forcing reply.",
    )
    data.setdefault("engine_line_idea", why_best or "Compress the engine line into the main positional idea.")
    data.setdefault("coach_question", "What is your opponent's most forcing move if you play your intended move?")
    if not isinstance(data.get("how_to_find"), list):
        data["how_to_find"] = [
            "Check forcing moves first",
            "Compare candidate moves",
            "Ask what the best move prevents",
        ]
    data.setdefault("key_lesson", "Natural moves still need a forcing-move check.")
    return data


def _ensure_dict(data: dict, key: str) -> dict:
    value = data.get(key)
    if not isinstance(value, dict):
        value = {}
        data[key] = value
    return value
