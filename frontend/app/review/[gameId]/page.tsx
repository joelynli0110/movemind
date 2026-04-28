"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { pollGame } from "@/lib/api";
import type { AnalysisResult } from "@/lib/types";
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
} from "lucide-react";
import clsx from "clsx";

const GRADE_COLOR: Record<string, string> = {
  A: "text-green-400 bg-green-400/10 border-green-400/30",
  B: "text-blue-400 bg-blue-400/10 border-blue-400/30",
  C: "text-amber-400 bg-amber-400/10 border-amber-400/30",
  D: "text-red-400 bg-red-400/10 border-red-400/30",
};

type Tab = "overview" | "mistakes" | "training";

export default function ReviewPage() {
  const { gameId } = useParams<{ gameId: string }>();
  const router = useRouter();

  const [data, setData] = useState<AnalysisResult | null>(null);
  const [pollStatus, setPollStatus] = useState<"processing" | "complete" | "error">("processing");
  const [errorMsg, setErrorMsg] = useState("");

  const [currentMoveIndex, setCurrentMoveIndex] = useState(0);
  const [activeMistakeIndex, setActiveMistakeIndex] = useState<number | null>(null);
  const [tab, setTab] = useState<Tab>("overview");

  // Polling
  useEffect(() => {
    if (!gameId) return;
    let active = true;

    async function poll() {
      try {
        const resp = await pollGame(gameId);
        if (!active) return;
        if (resp.status === "complete" && resp.result) {
          setData(resp.result);
          setPollStatus("complete");
        } else if (resp.status === "error") {
          setErrorMsg(resp.error ?? "Analysis failed");
          setPollStatus("error");
        } else {
          setTimeout(poll, 2500);
        }
      } catch (e) {
        if (!active) return;
        setErrorMsg(e instanceof Error ? e.message : "Network error");
        setPollStatus("error");
      }
    }
    poll();
    return () => { active = false; };
  }, [gameId]);

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
    // Clear active mistake if user navigates away from it
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
          <h2 className="text-xl font-semibold">Analysis failed</h2>
          <p className="text-slate-400 text-sm">{errorMsg}</p>
          <button
            onClick={() => router.push("/")}
            className="mt-2 px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm hover:bg-slate-700 transition-colors"
          >
            Try another game
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
            <p className="font-semibold">Analyzing your game…</p>
            <p className="text-slate-500 text-sm">
              Running Stockfish + AI coach. Usually 30–60 seconds.
            </p>
          </div>
          <div className="flex flex-col gap-1.5 text-xs text-slate-600 max-w-xs mx-auto text-left">
            {[
              "Parsing game moves",
              "Stockfish engine analysis",
              "Identifying critical moments",
              "Generating coach explanations",
              "Building training plan",
            ].map((step) => (
              <div key={step} className="flex items-center gap-2">
                <span className="w-1 h-1 rounded-full bg-slate-600" />
                {step}
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  // ── Main review UI ──────────────────────────────────────────────────────
  const { game, critical_moments, game_summary, training_plan } = data;
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
          <span className="text-slate-500">vs</span>
          <span className="font-medium">{black}</span>
          <span className="text-slate-600 text-xs bg-slate-800 px-2 py-0.5 rounded-full">
            {result}
          </span>
          {opening && <span className="text-slate-600 text-xs hidden sm:block">{opening}</span>}
        </div>
      </header>

      {/* Main layout */}
      <div className="flex-1 flex flex-col lg:flex-row gap-0 overflow-hidden">
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
          />
        </div>

        {/* Right: Coach panel */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Tabs */}
          <div className="flex border-b border-slate-800 px-4">
            {(["overview", "mistakes", "training"] as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={clsx(
                  "px-4 py-3 text-sm font-medium border-b-2 transition-colors capitalize",
                  tab === t
                    ? "border-amber-500 text-amber-400"
                    : "border-transparent text-slate-500 hover:text-slate-300"
                )}
              >
                {t === "overview" ? "Overview" : t === "mistakes" ? `Mistakes (${critical_moments.length})` : "Training Plan"}
              </button>
            ))}
          </div>

          {/* Tab content */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {/* ── Overview Tab ── */}
            {tab === "overview" && (
              <div className="space-y-4">
                {/* Grade card */}
                <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 p-4 flex items-center justify-between">
                  <div>
                    <p className="text-xs text-slate-500 mb-1">Game accuracy grade</p>
                    <span
                      className={clsx(
                        "text-2xl font-bold px-3 py-1 rounded-lg border",
                        GRADE_COLOR[game_summary.accuracy_grade] ?? GRADE_COLOR.C
                      )}
                    >
                      {game_summary.accuracy_grade}
                    </span>
                  </div>
                  <div className="text-right text-sm">
                    <p className="text-slate-500 text-xs">{game.total_moves} moves</p>
                    <p className="text-slate-500 text-xs">{critical_moments.length} mistake{critical_moments.length !== 1 ? "s" : ""} flagged</p>
                  </div>
                </div>

                {/* Strength / Weakness */}
                <div className="grid grid-cols-1 gap-3">
                  <InfoCard
                    icon={Award}
                    iconClass="text-green-400"
                    label="Biggest strength"
                    text={game_summary.biggest_strength}
                  />
                  <InfoCard
                    icon={AlertCircle}
                    iconClass="text-red-400"
                    label="Biggest weakness"
                    text={game_summary.biggest_weakness}
                  />
                  <InfoCard
                    icon={BookOpen}
                    iconClass="text-blue-400"
                    label="Key concept to study"
                    text={game_summary.key_concept}
                  />
                  <InfoCard
                    icon={Zap}
                    iconClass="text-amber-400"
                    label="Opening tip"
                    text={game_summary.opening_tip}
                  />
                </div>

                {/* Jump to mistakes */}
                {critical_moments.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                      Critical moments — click to review
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
                            <p className="text-sm font-medium">Move {m.move_number}</p>
                            <p className="text-xs text-slate-500 font-mono">
                              {m.player_move} → {m.best_move}
                            </p>
                          </div>
                        </div>
                        <span className="text-xs text-red-400">
                          -{(m.eval_loss / 100).toFixed(1)} pawns
                        </span>
                      </button>
                    ))}
                  </div>
                )}

                {critical_moments.length === 0 && (
                  <div className="rounded-xl border border-green-400/20 bg-green-400/5 p-4 text-center text-green-400 text-sm">
                    No significant mistakes found. Excellent game!
                  </div>
                )}
              </div>
            )}

            {/* ── Mistakes Tab ── */}
            {tab === "mistakes" && (
              <div className="space-y-3">
                {critical_moments.length === 0 ? (
                  <p className="text-slate-500 text-sm text-center py-8">No mistakes flagged.</p>
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
                    />
                  ))
                )}
              </div>
            )}

            {/* ── Training Tab ── */}
            {tab === "training" && (
              <div className="space-y-4">
                {/* Focus concept */}
                <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-4 space-y-1.5">
                  <p className="text-xs text-amber-400 font-semibold uppercase tracking-wide">
                    This week's focus
                  </p>
                  <p className="text-lg font-semibold">{training_plan.focus_concept}</p>
                  <p className="text-slate-400 text-sm">{training_plan.focus_explanation}</p>
                </div>

                {/* Puzzle themes */}
                <Section icon={Zap} label="Puzzle themes to practice">
                  <div className="flex flex-wrap gap-2">
                    {training_plan.puzzle_themes.map((t) => (
                      <span
                        key={t}
                        className="text-xs bg-slate-800 border border-slate-700 rounded-full px-3 py-1 text-slate-300"
                      >
                        {t}
                      </span>
                    ))}
                  </div>
                </Section>

                {/* Pre-move checklist */}
                <Section icon={CheckSquare} label="Pre-move checklist (use every move)">
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

                {/* Weekly schedule */}
                <Section icon={Calendar} label="Weekly training schedule">
                  <div className="space-y-2">
                    {training_plan.weekly_schedule.map(({ day, task }) => (
                      <div
                        key={day}
                        className="flex gap-3 text-sm border-l-2 border-slate-700 pl-3"
                      >
                        <span className="text-slate-500 w-14 flex-shrink-0 text-xs pt-0.5">
                          {day}
                        </span>
                        <span className="text-slate-300">{task}</span>
                      </div>
                    ))}
                  </div>
                </Section>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Small helper components ─────────────────────────────────────────────────

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
