export interface PositionFeatures {
  material_balance: string;
  king_safety: string;
  pawn_structure: string;
  piece_activity: string;
  tactical_motifs: string[];
  open_files: string[];
}

export interface MistakeExplanation {
  mistake_category: string;
  mistake_label: string;
  engine_layer: {
    eval_summary: string;
    best_line: string;
    candidate_summary: string;
  };
  tactical_layer: {
    motif: string;
    explanation: string;
  };
  strategic_layer: {
    concept: string;
    explanation: string;
  };
  human_layer: {
    likely_thought: string;
    correction: string;
  };
  engine_line_idea: string;
  coach_question: string;
  how_to_find: string[];
  key_lesson: string;
  why_player_move?: string;
  why_best_move?: string;
}

export type Severity = "blunder" | "mistake" | "inaccuracy" | "slight";
export type Language = "en" | "zh";

export interface EngineMove {
  move_index: number;
  move_number: number;
  color: string;
  player_move: string;
  best_move: string;
  eval_loss: number;
  severity: Severity;
  eval_before: number;
  eval_after_player: number;
  eval_after_best: number;
  pv_moves: string[];
  candidate_lines: CandidateLine[];
}

export interface CandidateLine {
  move: string;
  line: string[];
  centipawn: number | null;
  mate: number | null;
}

export interface CriticalMoment extends EngineMove {
  fen_before: string;
  explanation: MistakeExplanation | null;
  position_features: PositionFeatures;
}

export interface GameSummary {
  biggest_strength: string;
  biggest_weakness: string;
  key_concept: string;
  opening_tip: string;
  accuracy_grade: "A" | "B" | "C" | "D";
}

export interface TrainingDay {
  day: string;
  task: string;
}

export interface TrainingPlan {
  focus_concept?: string;
  focus_explanation?: string;
  puzzle_themes?: string[];
  pre_move_checklist?: string[];
  weekly_schedule?: TrainingDay[];
  puzzles?: TrainingPuzzle[];
}

export interface TrainingPuzzle {
  id: string;
  fen: string;
  move_number: number;
  side_to_move: string;
  prompt: string;
  solution: string;
  solution_line: string[];
  theme: string;
  source_mistake: string;
  label: string;
}

export interface GameInfo {
  moves_san: string[];
  fens: string[];
  player_color: "white" | "black";
  headers: Record<string, string>;
  total_moves: number;
}

export interface AnalysisResult {
  language: Language;
  game: GameInfo;
  engine_analysis: EngineMove[];         // all evaluated player moves, sorted by eval_loss desc
  critical_moments: CriticalMoment[];
  game_summary: GameSummary | null;
  training_plan: TrainingPlan | null;
  llm_available: boolean;
}

export interface AnalysisResponse {
  status: "processing" | "complete" | "error";
  result?: AnalysisResult;
  error?: string;
}
