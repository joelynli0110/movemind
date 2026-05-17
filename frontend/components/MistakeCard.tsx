"use client";

import type { CriticalMoment, Language } from "@/lib/types";
import { mistakeCardCopy } from "@/lib/i18n";
import { AlertTriangle, CheckCircle, Lightbulb, BookOpen, Cpu, Target, Brain } from "lucide-react";
import clsx from "clsx";

const SEVERITY_COLOR: Record<string, string> = {
  high: "text-red-400 border-red-400/30 bg-red-400/10",
  medium: "text-amber-400 border-amber-400/30 bg-amber-400/10",
  low: "text-yellow-400 border-yellow-400/30 bg-yellow-400/10",
};

interface Props {
  moment: CriticalMoment;
  index: number;
  active: boolean;
  onClick: () => void;
  language: Language;
}

export default function MistakeCard({ moment, index, active, onClick, language }: Props) {
  const { explanation, eval_loss, player_move, best_move, move_number, color } = moment;
  const severity = eval_loss >= 300 ? "high" : eval_loss >= 150 ? "medium" : "low";
  const t = mistakeCardCopy[language];
  const colorLabel = language === "zh" ? (color === "white" ? "白棋" : "黑棋") : color;
  const candidateLines = moment.candidate_lines ?? [];

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
      {/* Header — always visible */}
      <div className="px-4 py-3 flex items-start justify-between gap-3 border-b border-slate-700/40">
        <div className="flex items-center gap-2">
          <span className="w-6 h-6 rounded-full bg-slate-700 flex items-center justify-center text-xs font-bold text-slate-300">
            {index + 1}
          </span>
          <div>
            <div className="text-sm font-medium">
              {language === "zh" ? `${t.move} ${move_number} 手` : `${t.move} ${move_number}`}{" "}
              <span className="text-slate-400">({colorLabel})</span>
            </div>
            <div className="text-xs text-slate-500 mt-0.5">
              <span className="text-red-400 font-mono">{player_move}</span>
              {" -> "}
              <span className="text-green-400 font-mono">{best_move}</span>
            </div>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1.5">
          <span
            className={clsx(
              "text-xs font-medium px-2 py-0.5 rounded-full border",
              SEVERITY_COLOR[severity]
            )}
          >
            -{(eval_loss / 100).toFixed(1)} {t.pawns}
          </span>
          {explanation && (
            <span className="text-xs text-slate-500">
              {t.categories[explanation.mistake_category as keyof typeof t.categories] ?? explanation.mistake_category}
            </span>
          )}
        </div>
      </div>

      {/* Expanded body */}
      {active && (
        <div className="px-4 py-4 space-y-4 text-sm">
          {explanation ? (
            // ── LLM explanation available ───────────────────────────────────
            <>
              <div className="flex items-center gap-2 text-amber-300 font-medium">
                <AlertTriangle size={14} />
                {explanation.mistake_label}
              </div>

              <section className="space-y-1.5">
                <h4 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-400">
                  <Cpu size={11} />
                  {t.engineLayer}
                </h4>
                <p className="text-slate-300 leading-relaxed">{explanation.engine_layer.eval_summary}</p>
                {explanation.engine_layer.candidate_summary && (
                  <p className="text-slate-500 text-xs leading-relaxed">
                    {explanation.engine_layer.candidate_summary}
                  </p>
                )}
                {explanation.engine_layer.best_line && (
                  <p className="font-mono text-green-400 bg-slate-900/60 rounded px-2 py-1 text-xs">
                    {explanation.engine_layer.best_line}
                  </p>
                )}
              </section>

              <section className="space-y-1.5">
                <h4 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-400">
                  <Target size={11} />
                  {t.tacticalLayer}
                </h4>
                <p className="text-amber-300 text-xs">{explanation.tactical_layer.motif}</p>
                <p className="text-slate-300 leading-relaxed">{explanation.tactical_layer.explanation}</p>
              </section>

              <section className="space-y-1.5">
                <h4 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-400">
                  <CheckCircle size={11} />
                  {t.strategicLayer}
                </h4>
                <p className="text-blue-300 text-xs">{explanation.strategic_layer.concept}</p>
                <p className="text-slate-300 leading-relaxed">{explanation.strategic_layer.explanation}</p>
              </section>

              <section className="space-y-1.5">
                <h4 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-400">
                  <Brain size={11} />
                  {t.humanLayer}
                </h4>
                <p className="text-slate-300 leading-relaxed">{explanation.human_layer.likely_thought}</p>
                <p className="text-slate-400 leading-relaxed">{explanation.human_layer.correction}</p>
              </section>

              {explanation.coach_question && (
                <div className="rounded-lg border border-blue-400/20 bg-blue-400/5 px-3 py-2.5 text-xs text-blue-100">
                  <span className="font-semibold text-blue-300">{t.coachQuestion}: </span>
                  {explanation.coach_question}
                </div>
              )}

              <section className="space-y-2">
                <h4 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-400">
                  <Lightbulb size={11} />
                  {t.howToFind}
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

              <div className="flex items-start gap-2 bg-slate-700/40 rounded-lg px-3 py-2.5 border border-slate-600/30">
                <BookOpen size={13} className="text-amber-400 mt-0.5 flex-shrink-0" />
                <p className="text-slate-300 text-xs leading-relaxed">
                  <span className="font-semibold text-amber-400">{t.keyLesson}</span>
                  {explanation.key_lesson}
                </p>
              </div>

              {explanation.engine_line_idea && (
                <p className="text-slate-500 italic text-xs">{explanation.engine_line_idea}</p>
              )}
            </>
          ) : (
            // ── Engine-only (no LLM) ────────────────────────────────────────
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-slate-400 text-xs bg-slate-800 border border-slate-700 rounded-lg px-3 py-2">
                <Cpu size={12} />
                {t.unavailable}
              </div>
              {moment.pv_moves.length > 0 && (
                <div className="text-xs space-y-1">
                  <p className="text-slate-500 uppercase tracking-wide font-semibold">{t.engineBestLine}</p>
                  <p className="font-mono text-green-400 bg-slate-900/60 rounded px-2 py-1">
                    {moment.pv_moves.join(" ")}
                  </p>
                </div>
              )}
              {candidateLines.length > 0 && (
                <div className="text-xs space-y-1">
                  <p className="text-slate-500 uppercase tracking-wide font-semibold">{t.candidateLines}</p>
                  <div className="space-y-1">
                    {candidateLines.slice(0, 3).map((candidate, i) => (
                      <p key={`${candidate.move}-${i}`} className="font-mono text-slate-300 bg-slate-900/60 rounded px-2 py-1">
                        {i + 1}. {candidate.line.join(" ") || candidate.move}
                      </p>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Position features — always shown */}
          <details className="text-xs">
            <summary className="cursor-pointer text-slate-500 hover:text-slate-400 select-none">
              {t.positionDetails}
            </summary>
            <div className="mt-2 space-y-1 text-slate-500 bg-slate-900/40 rounded-lg px-3 py-2">
              <p><span className="text-slate-400">{t.material}:</span> {moment.position_features.material_balance}</p>
              <p><span className="text-slate-400">{t.kingSafety}:</span> {moment.position_features.king_safety}</p>
              {moment.position_features.tactical_motifs.length > 0 && (
                <p>
                  <span className="text-slate-400">{t.tacticalMotifs}:</span>{" "}
                  {moment.position_features.tactical_motifs.join(", ")}
                </p>
              )}
              {moment.pv_moves.length > 0 && (
                <p>
                  <span className="text-slate-400">{t.bestLine}:</span>{" "}
                  <span className="font-mono text-green-400">{moment.pv_moves.join(" ")}</span>
                </p>
              )}
              {candidateLines.length > 0 && (
                <div>
                  <span className="text-slate-400">{t.candidateLines}:</span>
                  <div className="mt-1 space-y-1">
                    {candidateLines.slice(0, 3).map((candidate, i) => (
                      <p key={`${candidate.move}-${i}`} className="font-mono text-slate-400">
                        {i + 1}. {candidate.line.join(" ") || candidate.move}
                      </p>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </details>
        </div>
      )}
    </div>
  );
}
