"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { pollGame } from "@/lib/api";
import { normalizeLanguage, reviewCopy, severityLabels } from "@/lib/i18n";
import type { AnalysisResult, Language } from "@/lib/types";
import ChessBoardViewer from "@/components/ChessBoard";
import MistakeCard from "@/components/MistakeCard";
import {
  Award,
  AlertCircle,
  BookOpen,
  Calendar,
  ArrowLeft,
  CheckSquare,
  Zap,
  Cpu,
} from "lucide-react";
import clsx from "clsx";

const GRADE_COLOR: Record<string, string> = {
  A: "text-green-400 bg-green-400/10 border-green-400/30",
  B: "text-blue-400 bg-blue-400/10 border-blue-400/30",
  C: "text-amber-400 bg-amber-400/10 border-amber-400/30",
  D: "text-red-400 bg-red-400/10 border-red-400/30",
};

type Tab = "overview" | "engine" | "mistakes" | "training";

const SEVERITY_STYLE: Record<string, string> = {
  blunder:    "text-red-400 bg-red-400/10 border-red-400/30",
  mistake:    "text-orange-400 bg-orange-400/10 border-orange-400/30",
  inaccuracy: "text-amber-400 bg-amber-400/10 border-amber-400/30",
  slight:     "text-slate-400 bg-slate-700/40 border-slate-600",
};

const POLL_INTERVAL_MS = 2500;
const POLL_REQUEST_TIMEOUT_MS = 10000;
const MAX_ANALYSIS_WAIT_MS = 180000;

export default function ReviewPage() {
  const { gameId } = useParams<{ gameId: string }>();
  const router = useRouter();
  const searchParams = useSearchParams();
  const requestedLanguage = normalizeLanguage(searchParams.get("lang"));

  const [data, setData] = useState<AnalysisResult | null>(null);
  const [pollStatus, setPollStatus] = useState<"processing" | "complete" | "error">("processing");
  const [errorMsg, setErrorMsg] = useState("");

  const [currentMoveIndex, setCurrentMoveIndex] = useState(0);
  const [activeMistakeIndex, setActiveMistakeIndex] = useState<number | null>(null);
  const [tab, setTab] = useState<Tab>("overview");
  const language: Language = data?.language ?? requestedLanguage;
  const t = reviewCopy[language];

  // Polling
  useEffect(() => {
    if (!gameId) return;
    let active = true;
    let pollTimer: ReturnType<typeof setTimeout> | undefined;
    const startedAt = Date.now();

    async function poll() {
      const controller = new AbortController();
      const requestTimer = setTimeout(() => controller.abort(), POLL_REQUEST_TIMEOUT_MS);

      try {
        const resp = await pollGame(gameId, { signal: controller.signal });
        if (!active) return;
        if (resp.status === "complete" && resp.result) {
          setData(resp.result);
          setPollStatus("complete");
        } else if (resp.status === "error") {
          setErrorMsg(resp.error ?? t.status.failed);
          setPollStatus("error");
        } else if (Date.now() - startedAt > MAX_ANALYSIS_WAIT_MS) {
          setErrorMsg(t.status.timeout);
          setPollStatus("error");
        } else {
          pollTimer = setTimeout(poll, POLL_INTERVAL_MS);
        }
      } catch (e) {
        if (!active) return;
        setErrorMsg(e instanceof Error && e.name === "AbortError"
          ? t.status.requestTimeout
          : e instanceof Error ? e.message : t.status.network);
        setPollStatus("error");
      } finally {
        clearTimeout(requestTimer);
      }
    }
    poll();
    return () => {
      active = false;
      if (pollTimer) clearTimeout(pollTimer);
    };
  }, [gameId, t]);

  const jumpToMistake = useCallback(
    (idx: number) => {
      if (!data) return;
      const moment = data.critical_moments[idx];
      setCurrentMoveIndex(moment.move_index);
      setActiveMistakeIndex(idx);
      setTab("mistakes");
    },
    [data]
  );

  const handleIndexChange = useCallback((idx: number) => {
    setCurrentMoveIndex(idx);
    setActiveMistakeIndex((prev) => {
      if (prev === null || !data) return prev;
      const m = data.critical_moments[prev];
      return m && idx === m.move_index ? prev : null;
    });
  }, [data]);

  // ── Loading / error states ──────────────────────────────────────────────
  if (pollStatus === "error") {
    return (
      <div className="min-h-screen flex items-center justify-center p-8">
        <div className="text-center space-y-4 max-w-md">
          <AlertCircle size={40} className="text-red-400 mx-auto" />
          <h2 className="text-xl font-semibold">{t.status.failed}</h2>
          <p className="text-slate-400 text-sm">{errorMsg}</p>
          <button
            onClick={() => router.push("/")}
            className="mt-2 px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm hover:bg-slate-700 transition-colors"
          >
            {t.status.tryAnother}
          </button>
        </div>
      </div>
    );
  }

  if (pollStatus === "processing" || !data) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center space-y-5">
          <div className="w-14 h-14 border-4 border-slate-700 border-t-amber-400 rounded-full animate-spin mx-auto" />
          <div className="space-y-1.5">
            <p className="font-semibold">{t.status.analyzing}</p>
            <p className="text-slate-500 text-sm">{t.status.running}</p>
          </div>
        </div>
      </div>
    );
  }

  // ── Main review UI ──────────────────────────────────────────────────────
  const {
    game,
    engine_analysis = [],
    critical_moments = [],
    game_summary = null,
    training_plan = null,
    llm_available = false,
  } = data ?? {};

  if (!game) return null;   // still loading — handled above, but satisfies TS

  const white = game.headers.White ?? "White";
  const black = game.headers.Black ?? "Black";
  const result = game.headers.Result ?? "*";
  const opening = game.headers.Opening ?? game.headers.ECO ?? "";

  return (
    <div className="min-h-screen flex flex-col">
      {/* Top bar */}
      <header className="border-b border-slate-800 px-4 py-3 flex items-center gap-3">
        <button
          onClick={() => router.push("/")}
          className="p-1.5 hover:bg-slate-800 rounded-lg transition-colors"
        >
          <ArrowLeft size={16} className="text-slate-400" />
        </button>
        <div className="w-6 h-6 rounded bg-amber-500 flex items-center justify-center font-bold text-gray-900 text-xs">
          M
        </div>
        <div className="flex items-center gap-2 text-sm">
          <span className="font-medium">{white}</span>
          <span className="text-slate-500">{language === "zh" ? "对" : "vs"}</span>
          <span className="font-medium">{black}</span>
          <span className="text-slate-600 text-xs bg-slate-800 px-2 py-0.5 rounded-full">{result}</span>
          {opening && <span className="text-slate-600 text-xs hidden sm:block">{opening}</span>}
        </div>
      </header>

      {/* Main layout */}
      <div className="flex-1 flex flex-col lg:flex-row overflow-hidden">
        {/* Left: Chess board */}
        <div className="lg:w-[480px] flex-shrink-0 p-4 lg:border-r border-slate-800">
          <ChessBoardViewer
            fens={game.fens}
            movesSan={game.moves_san}
            currentIndex={currentMoveIndex}
            playerColor={game.player_color}
            criticalMoments={critical_moments}
            activeMistakeIndex={activeMistakeIndex}
            onIndexChange={handleIndexChange}
            language={language}
          />
        </div>

        {/* Right: Coach panel */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Tabs */}
          <div className="flex border-b border-slate-800 px-4">
            {(["overview", "engine", "mistakes", "training"] as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={clsx(
                  "px-3 py-3 text-sm font-medium border-b-2 transition-colors",
                  tab === t
                    ? "border-amber-500 text-amber-400"
                    : "border-transparent text-slate-500 hover:text-slate-300"
                )}
              >
                {t === "overview" ? reviewCopy[language].tabs.overview
                  : t === "engine" ? reviewCopy[language].tabs.engine
                  : t === "mistakes" ? `${reviewCopy[language].tabs.mistakes} (${critical_moments.length})`
                  : reviewCopy[language].tabs.training}
              </button>
            ))}
          </div>

          {/* Tab content */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">

            {/* ── Overview ── */}
            {tab === "overview" && (
              <div className="space-y-4">
                {/* LLM unavailable notice */}
                {!llm_available && (
                  <LlmNotice language={language} />
                )}

                {/* Engine stats — always shown */}
                <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 p-4 flex items-center justify-between">
                  <div className="space-y-0.5">
                    <p className="text-xs text-slate-500">{t.overview.engineAnalysis}</p>
                    <p className="font-semibold">
                      {critical_moments.length === 0
                        ? t.overview.noSignificant
                        : t.overview.mistakesFound(critical_moments.length)}
                    </p>
                  </div>
                  <div className="text-right text-xs text-slate-500">
                    <p>{t.overview.moves(game.total_moves)}</p>
                    <p>{t.overview.playingAs(game.player_color)}</p>
                  </div>
                </div>

                {/* LLM summary cards — only when available */}
                {game_summary && (
                  <>
                    <div className="flex items-center justify-between">
                      <p className="text-xs text-slate-500 uppercase tracking-wide font-semibold">
                        {t.overview.coachSummary}
                      </p>
                      <span className="text-xs text-slate-600 font-mono bg-slate-800 px-2 py-0.5 rounded">
                        {process.env.NEXT_PUBLIC_LLM_PROVIDER ?? "ollama"}
                      </span>
                      <span
                        className={clsx(
                          "text-sm font-bold px-2.5 py-0.5 rounded-lg border",
                          GRADE_COLOR[game_summary.accuracy_grade] ?? GRADE_COLOR.C
                        )}
                      >
                        {t.overview.grade(game_summary.accuracy_grade)}
                      </span>
                    </div>
                    <div className="grid grid-cols-1 gap-3">
                      <InfoCard icon={Award} iconClass="text-green-400" label={t.overview.biggestStrength} text={game_summary.biggest_strength} />
                      <InfoCard icon={AlertCircle} iconClass="text-red-400" label={t.overview.biggestWeakness} text={game_summary.biggest_weakness} />
                      <InfoCard icon={BookOpen} iconClass="text-blue-400" label={t.overview.keyConcept} text={game_summary.key_concept} />
                      <InfoCard icon={Zap} iconClass="text-amber-400" label={t.overview.openingTip} text={game_summary.opening_tip} />
                    </div>
                  </>
                )}

                {/* Jump-to buttons — always shown when mistakes exist */}
                {critical_moments.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                      {t.overview.criticalMoments}
                    </p>
                    {critical_moments.map((m, i) => (
                      <button
                        key={i}
                        onClick={() => jumpToMistake(i)}
                        className="w-full text-left flex items-center justify-between gap-3 bg-slate-800/60 border border-slate-700/40 hover:border-amber-500/40 rounded-xl px-4 py-3 transition-colors"
                      >
                        <div className="flex items-center gap-3">
                          <span className="w-6 h-6 rounded-full bg-slate-700 flex items-center justify-center text-xs font-bold text-slate-300">
                            {i + 1}
                          </span>
                          <div>
                            <p className="text-sm font-medium">
                              {language === "zh" ? `${t.overview.move} ${m.move_number} 手` : `${t.overview.move} ${m.move_number}`}
                            </p>
                            <p className="text-xs text-slate-500 font-mono">
                              {m.player_move} → {m.best_move}
                            </p>
                          </div>
                        </div>
                        <span className="text-xs text-red-400">
                          -{(m.eval_loss / 100).toFixed(1)} {t.overview.pawns}
                        </span>
                      </button>
                    ))}
                  </div>
                )}

                {critical_moments.length === 0 && (
                  <div className="rounded-xl border border-green-400/20 bg-green-400/5 p-4 text-center text-green-400 text-sm">
                    {t.overview.noMistakesFound}
                  </div>
                )}
              </div>
            )}

            {/* ── Engine Tab ── */}
            {tab === "engine" && (
              <div className="space-y-3">
                <p className="text-xs text-slate-500 uppercase tracking-wide font-semibold">
                  {t.engine.heading}
                </p>
                {engine_analysis.length === 0 ? (
                  <p className="text-slate-500 text-sm py-6 text-center">
                    {t.engine.unavailable}
                  </p>
                ) : (
                  <div className="rounded-xl border border-slate-700/40 overflow-hidden">
                    {/* Header */}
                    <div className="grid grid-cols-[2rem_1fr_1fr_1fr_auto] gap-2 px-3 py-2 bg-slate-800/60 text-xs text-slate-500 font-medium uppercase tracking-wide">
                      <span>{t.engine.number}</span>
                      <span>{t.engine.yourMove}</span>
                      <span>{t.engine.bestMove}</span>
                      <span>{t.engine.bestLine}</span>
                      <span>{t.engine.loss}</span>
                    </div>
                    {engine_analysis.map((m, i) => (
                      <button
                        key={i}
                        onClick={() => {
                          setCurrentMoveIndex(m.move_index);
                          // If this move is one of the critical moments, highlight it
                          const ci = critical_moments.findIndex(c => c.move_index === m.move_index);
                          if (ci >= 0) {
                            setActiveMistakeIndex(ci);
                            setTab("mistakes");
                          }
                        }}
                        className="w-full grid grid-cols-[2rem_1fr_1fr_1fr_auto] gap-2 items-center px-3 py-2.5 border-t border-slate-700/30 hover:bg-slate-700/30 transition-colors text-left"
                      >
                        <span className="text-xs text-slate-600">{m.move_number}{m.color === "white" ? "." : "..."}</span>
                        <span className="font-mono text-sm text-red-400">{m.player_move}</span>
                        <span className="font-mono text-sm text-green-400">{m.best_move}</span>
                        <span className="font-mono text-xs text-slate-400 truncate">
                          {m.pv_moves.slice(0, 3).join(" ") || "-"}
                        </span>
                        <span className={clsx(
                          "text-xs font-medium px-2 py-0.5 rounded-full border whitespace-nowrap",
                          SEVERITY_STYLE[m.severity]
                        )}>
                          {m.severity === "slight"
                            ? `-${(m.eval_loss / 100).toFixed(1)}`
                            : `${severityLabels[language][m.severity]} -${(m.eval_loss / 100).toFixed(1)}`}
                        </span>
                      </button>
                    ))}
                  </div>
                )}
                <p className="text-xs text-slate-600">
                  {t.engine.note}
                </p>
              </div>
            )}

            {/* ── Mistakes ── */}
            {tab === "mistakes" && (
              <div className="space-y-3">
                {!llm_available && <LlmNotice language={language} />}
                {critical_moments.length === 0 ? (
                  <p className="text-slate-500 text-sm text-center py-8">{t.mistakes.empty}</p>
                ) : (
                  critical_moments.map((m, i) => (
                    <MistakeCard
                      key={i}
                      moment={m}
                      index={i}
                      active={activeMistakeIndex === i}
                      onClick={() => {
                        setActiveMistakeIndex(i);
                        setCurrentMoveIndex(m.move_index);
                      }}
                      language={language}
                    />
                  ))
                )}
              </div>
            )}

            {/* ── Training Plan ── */}
            {tab === "training" && (
              <div className="space-y-4">
                {training_plan ? (
                  <>
                    {training_plan.focus_concept && (
                      <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-4 space-y-1.5">
                        <p className="text-xs text-amber-400 font-semibold uppercase tracking-wide">
                          {t.training.focus}
                        </p>
                        <p className="text-lg font-semibold">{training_plan.focus_concept}</p>
                        {training_plan.focus_explanation && (
                          <p className="text-slate-400 text-sm">{training_plan.focus_explanation}</p>
                        )}
                      </div>
                    )}

                    {training_plan.puzzle_themes && training_plan.puzzle_themes.length > 0 && (
                      <Section icon={Zap} label={t.training.puzzleThemes}>
                        <div className="flex flex-wrap gap-2">
                          {training_plan.puzzle_themes.map((theme) => (
                            <span key={theme} className="text-xs bg-slate-800 border border-slate-700 rounded-full px-3 py-1 text-slate-300">
                              {theme}
                            </span>
                          ))}
                        </div>
                      </Section>
                    )}

                    {training_plan.pre_move_checklist && training_plan.pre_move_checklist.length > 0 && (
                      <Section icon={CheckSquare} label={t.training.checklist}>
                        <ul className="space-y-2">
                          {training_plan.pre_move_checklist.map((q, i) => (
                            <li key={i} className="flex items-start gap-2.5 text-sm text-slate-300">
                              <span className="mt-0.5 w-4 h-4 border border-amber-500/50 rounded flex items-center justify-center text-[10px] text-amber-400 font-bold flex-shrink-0">
                                {i + 1}
                              </span>
                              {q}
                            </li>
                          ))}
                        </ul>
                      </Section>
                    )}

                    {training_plan.puzzles && training_plan.puzzles.length > 0 && (
                      <Section icon={BookOpen} label={t.training.reviewPuzzles}>
                        <div className="space-y-2">
                          {training_plan.puzzles.map((puzzle, i) => (
                            <div key={puzzle.id} className="rounded-xl border border-slate-700/40 bg-slate-800/40 px-4 py-3 space-y-2">
                              <div className="flex items-start justify-between gap-3">
                                <div>
                                  <p className="text-sm font-medium">
                                    {i + 1}. {puzzle.label}
                                  </p>
                                  <p className="text-xs text-slate-500">
                                    {t.overview.move} {puzzle.move_number} · {puzzle.side_to_move}
                                  </p>
                                </div>
                                <span className="text-xs text-slate-500 font-mono">
                                  {puzzle.theme}
                                </span>
                              </div>
                              <p className="text-sm text-slate-300">{puzzle.prompt}</p>
                              <div className="grid gap-1 text-xs text-slate-500 sm:grid-cols-2">
                                <p>
                                  <span className="text-slate-400">{t.training.sourceMistake}:</span>{" "}
                                  <span className="font-mono text-red-400">{puzzle.source_mistake}</span>
                                </p>
                                <p>
                                  <span className="text-slate-400">{t.training.solution}:</span>{" "}
                                  <span className="font-mono text-green-400">{puzzle.solution}</span>
                                </p>
                              </div>
                              {puzzle.solution_line.length > 0 && (
                                <p className="text-xs">
                                  <span className="text-slate-500">{t.training.solutionLine}: </span>
                                  <span className="font-mono text-green-400">{puzzle.solution_line.join(" ")}</span>
                                </p>
                              )}
                            </div>
                          ))}
                        </div>
                      </Section>
                    )}

                    {training_plan.weekly_schedule && training_plan.weekly_schedule.length > 0 && (
                      <Section icon={Calendar} label={t.training.weekly}>
                        <div className="space-y-2">
                          {training_plan.weekly_schedule.map(({ day, task }) => (
                            <div key={day} className="flex gap-3 text-sm border-l-2 border-slate-700 pl-3">
                              <span className="text-slate-500 w-14 flex-shrink-0 text-xs pt-0.5">{day}</span>
                              <span className="text-slate-300">{task}</span>
                            </div>
                          ))}
                        </div>
                      </Section>
                    )}
                  </>
                ) : (
                  <LlmNotice language={language} />
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Helper components ───────────────────────────────────────────────────────

function LlmNotice({ language }: { language: Language }) {
  const t = reviewCopy[language];
  return (
    <div className="flex items-start gap-2.5 bg-slate-800/60 border border-slate-700 rounded-xl px-4 py-3 text-sm text-slate-400">
      <Cpu size={14} className="mt-0.5 flex-shrink-0 text-slate-500" />
      <span>{t.llmNotice}</span>
    </div>
  );
}

function InfoCard({
  icon: Icon,
  iconClass,
  label,
  text,
}: {
  icon: React.ElementType;
  iconClass: string;
  label: string;
  text: string;
}) {
  return (
    <div className="flex items-start gap-3 bg-slate-800/40 border border-slate-700/40 rounded-xl px-4 py-3">
      <Icon size={15} className={clsx(iconClass, "mt-0.5 flex-shrink-0")} />
      <div>
        <p className="text-xs text-slate-500 mb-0.5">{label}</p>
        <p className="text-sm text-slate-300">{text}</p>
      </div>
    </div>
  );
}

function Section({
  icon: Icon,
  label,
  children,
}: {
  icon: React.ElementType;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2.5">
      <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
        <Icon size={12} />
        {label}
      </h3>
      {children}
    </div>
  );
}
