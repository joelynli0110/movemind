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
  why_player_move: string;
  why_best_move: string;
  engine_line_idea: string;
  how_to_find: string[];
  key_lesson: string;
}

export interface CriticalMoment {
  move_index: number;    // 0-based index into moves_san
  move_number: number;   // full-move number shown in chess notation
  color: string;
  fen_before: string;
  player_move: string;
  best_move: string;
  eval_loss: number;
  pv_moves: string[];
  explanation: MistakeExplanation;
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
  focus_concept: string;
  focus_explanation: string;
  puzzle_themes: string[];
  pre_move_checklist: string[];
  weekly_schedule: TrainingDay[];
}

export interface GameInfo {
  moves_san: string[];
  fens: string[];          // fens[0] = start; fens[i] = after moves_san[i-1]
  player_color: "white" | "black";
  headers: Record<string, string>;
  total_moves: number;
}

export interface AnalysisResult {
  game: GameInfo;
  critical_moments: CriticalMoment[];
  game_summary: GameSummary;
  training_plan: TrainingPlan;
}

export interface AnalysisResponse {
  status: "processing" | "complete" | "error";
  result?: AnalysisResult;
  error?: string;
}
