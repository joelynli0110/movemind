"use client";

import type { CriticalMoment } from "@/lib/types";
import { AlertTriangle, CheckCircle, Lightbulb, BookOpen } from "lucide-react";
import clsx from "clsx";

const CATEGORY_LABELS: Record<string, string> = {
  tactical_blindness: "Tactical Blindness",
  king_safety_neglect: "King Safety Neglect",
  wrong_trade: "Wrong Trade",
  premature_attack: "Premature Attack",
  passive_play: "Passive Play",
  pawn_structure_error: "Pawn Structure Error",
  missed_tactic: "Missed Tactic",
  strategic_misunderstanding: "Strategic Error",
};

const GRADE_COLOR: Record<string, string> = {
  high: "text-red-400 border-red-400/30 bg-red-400/10",
  medium: "text-amber-400 border-amber-400/30 bg-amber-400/10",
  low: "text-yellow-400 border-yellow-400/30 bg-yellow-400/10",
};

interface Props {
  moment: CriticalMoment;
  index: number;
  active: boolean;
  onClick: () => void;
}

export default function MistakeCard({ moment, index, active, onClick }: Props) {
  const { explanation, eval_loss, player_move, best_move, move_number, color } = moment;
  const severity = eval_loss >= 300 ? "high" : eval_loss >= 150 ? "medium" : "low";
  const label = CATEGORY_LABELS[explanation.mistake_category] ?? explanation.mistake_category;

  return (
    <div
      onClick={onClick}
      className={clsx(
        "rounded-xl border cursor-pointer transition-all duration-200 overflow-hidden",
        active
          ? "border-amber-500/50 bg-amber-500/5"
          : "border-slate-700/60 bg-slate-800/40 hover:border-slate-600"
      )}
    >
      {/* Header */}
      <div className="px-4 py-3 flex items-start justify-between gap-3 border-b border-slate-700/40">
        <div className="flex items-center gap-2">
          <span className="w-6 h-6 rounded-full bg-slate-700 flex items-center justify-center text-xs font-bold text-slate-300">
            {index + 1}
          </span>
          <div>
            <div className="text-sm font-medium">
              Move {move_number}{" "}
              <span className="text-slate-400">({color})</span>
            </div>
            <div className="text-xs text-slate-500 mt-0.5">
              <span className="text-red-400 font-mono">{player_move}</span>
              {" → "}
              <span className="text-green-400 font-mono">{best_move}</span>
            </div>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1.5">
          <span
            className={clsx(
              "text-xs font-medium px-2 py-0.5 rounded-full border",
              GRADE_COLOR[severity]
            )}
          >
            -{Math.round(eval_loss / 100 * 10) / 10} pawns
          </span>
          <span className="text-xs text-slate-500">{label}</span>
        </div>
      </div>

      {/* Body — only show when active */}
      {active && (
        <div className="px-4 py-4 space-y-4 text-sm">
          {/* Mistake label */}
          <div className="flex items-center gap-2 text-amber-300 font-medium">
            <AlertTriangle size={14} />
            {explanation.mistake_label}
          </div>

          {/* Why my move was wrong */}
          <section className="space-y-1.5">
            <h4 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-400">
              <AlertTriangle size={11} />
              Why your move was wrong
            </h4>
            <p className="text-slate-300 leading-relaxed">{explanation.why_player_move}</p>
          </section>

          {/* Why best move works */}
          <section className="space-y-1.5">
            <h4 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-400">
              <CheckCircle size={11} />
              Why {best_move} is correct
            </h4>
            <p className="text-slate-300 leading-relaxed">{explanation.why_best_move}</p>
            {explanation.engine_line_idea && (
              <p className="text-slate-500 italic text-xs">{explanation.engine_line_idea}</p>
            )}
          </section>

          {/* How to find it next time */}
          <section className="space-y-2">
            <h4 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-400">
              <Lightbulb size={11} />
              How to find it next time
            </h4>
            <ul className="space-y-1.5">
              {explanation.how_to_find.map((rule, i) => (
                <li key={i} className="flex items-start gap-2 text-slate-300">
                  <span className="mt-0.5 w-4 h-4 rounded-full bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-[10px] font-bold text-amber-400 flex-shrink-0">
                    {i + 1}
                  </span>
                  {rule}
                </li>
              ))}
            </ul>
          </section>

          {/* Key lesson */}
          <div className="flex items-start gap-2 bg-slate-700/40 rounded-lg px-3 py-2.5 border border-slate-600/30">
            <BookOpen size={13} className="text-amber-400 mt-0.5 flex-shrink-0" />
            <p className="text-slate-300 text-xs leading-relaxed">
              <span className="font-semibold text-amber-400">Key lesson: </span>
              {explanation.key_lesson}
            </p>
          </div>

          {/* Position features (collapsed detail) */}
          <details className="text-xs">
            <summary className="cursor-pointer text-slate-500 hover:text-slate-400 select-none">
              Position details
            </summary>
            <div className="mt-2 space-y-1 text-slate-500 bg-slate-900/40 rounded-lg px-3 py-2">
              <p><span className="text-slate-400">Material:</span> {moment.position_features.material_balance}</p>
              <p><span className="text-slate-400">King safety:</span> {moment.position_features.king_safety}</p>
              {moment.position_features.tactical_motifs.length > 0 && (
                <p>
                  <span className="text-slate-400">Tactical motifs:</span>{" "}
                  {moment.position_features.tactical_motifs.join(", ")}
                </p>
              )}
              {moment.pv_moves.length > 0 && (
                <p>
                  <span className="text-slate-400">Best line:</span>{" "}
                  <span className="font-mono">{moment.pv_moves.join(" ")}</span>
                </p>
              )}
            </div>
          </details>
        </div>
      )}
    </div>
  );
}
