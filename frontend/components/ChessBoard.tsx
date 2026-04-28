"use client";

/**
 * Interactive chess board with move navigation.
 * Uses react-chessboard + chess.js.
 *
 * Shows red arrow for the player's bad move and green arrow for the best move
 * when the board is positioned at a critical moment.
 */
import { useCallback, useEffect, useRef } from "react";
import dynamic from "next/dynamic";
import { Chess } from "chess.js";
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from "lucide-react";
import type { CriticalMoment } from "@/lib/types";

const Chessboard = dynamic(
  () => import("react-chessboard").then((m) => m.Chessboard),
  { ssr: false }
);

interface Props {
  fens: string[];           // fens[0] = start, fens[i] = after move i-1
  movesSan: string[];
  currentIndex: number;     // index into fens array
  playerColor: "white" | "black";
  criticalMoments: CriticalMoment[];
  activeMistakeIndex: number | null;
  onIndexChange: (idx: number) => void;
}

export default function ChessBoardViewer({
  fens,
  movesSan,
  currentIndex,
  playerColor,
  criticalMoments,
  activeMistakeIndex,
  onIndexChange,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);

  const fen = fens[currentIndex] ?? fens[0];
  const total = movesSan.length;
  const canBack = currentIndex > 0;
  const canForward = currentIndex < total;

  // Arrow highlighting for the active mistake
  const arrows = useCallback((): [string, string, string?][] => {
    if (activeMistakeIndex === null) return [];
    const moment = criticalMoments[activeMistakeIndex];
    if (!moment) return [];

    // We're at the "before" position — show player's move (red) and best move (green)
    if (currentIndex !== moment.move_index) return [];

    const arrs: [string, string, string?][] = [];
    try {
      const chess = new Chess(moment.fen_before);

      // Player's move — red
      const playerMove = chess.move(moment.player_move, { strict: false });
      if (playerMove) {
        arrs.push([playerMove.from, playerMove.to, "rgba(220,38,38,0.8)"]);
        chess.undo();
      }

      // Best move — green
      const bestMove = chess.move(moment.best_move, { strict: false });
      if (bestMove) {
        arrs.push([bestMove.from, bestMove.to, "rgba(34,197,94,0.8)"]);
      }
    } catch {
      // SAN parse can fail in edge cases; just show no arrows
    }
    return arrs;
  }, [activeMistakeIndex, criticalMoments, currentIndex]);

  // Square highlight for the last played move
  const squareStyles = useCallback((): Record<string, React.CSSProperties> => {
    const styles: Record<string, React.CSSProperties> = {};
    if (currentIndex === 0) return styles;

    try {
      const chess = new Chess(fens[currentIndex - 1]);
      const san = movesSan[currentIndex - 1];
      const move = chess.move(san, { strict: false });
      if (move) {
        const highlight = { backgroundColor: "rgba(251,191,36,0.25)" };
        styles[move.from] = highlight;
        styles[move.to] = highlight;
      }
    } catch { /* ignore */ }
    return styles;
  }, [currentIndex, fens, movesSan]);

  // Keyboard navigation
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "ArrowLeft" && canBack) onIndexChange(currentIndex - 1);
      if (e.key === "ArrowRight" && canForward) onIndexChange(currentIndex + 1);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [canBack, canForward, currentIndex, onIndexChange]);

  // Map move index → whether it's a mistake
  const mistakeIndices = new Set(criticalMoments.map((m) => m.move_index));

  return (
    <div className="flex flex-col gap-3" ref={containerRef}>
      {/* Board */}
      <div className="rounded-xl overflow-hidden shadow-2xl">
        <Chessboard
          position={fen}
          boardOrientation={playerColor}
          arePiecesDraggable={false}
          customArrows={arrows()}
          customSquareStyles={squareStyles()}
          customDarkSquareStyle={{ backgroundColor: "#b58863" }}
          customLightSquareStyle={{ backgroundColor: "#f0d9b5" }}
          boardWidth={420}
        />
      </div>

      {/* Navigation controls */}
      <div className="flex items-center justify-between bg-slate-800/60 rounded-xl px-3 py-2 border border-slate-700/40">
        <div className="flex items-center gap-1">
          <NavBtn icon={ChevronsLeft} disabled={!canBack} onClick={() => onIndexChange(0)} title="Start" />
          <NavBtn icon={ChevronLeft} disabled={!canBack} onClick={() => onIndexChange(currentIndex - 1)} title="Previous (←)" />
          <NavBtn icon={ChevronRight} disabled={!canForward} onClick={() => onIndexChange(currentIndex + 1)} title="Next (→)" />
          <NavBtn icon={ChevronsRight} disabled={!canForward} onClick={() => onIndexChange(total)} title="End" />
        </div>
        <span className="text-xs text-slate-500 font-mono">
          {currentIndex === 0 ? "Start" : `${Math.ceil(currentIndex / 2)}.${currentIndex % 2 === 1 ? "" : "."} ${movesSan[currentIndex - 1] ?? ""}`}
        </span>
      </div>

      {/* Compact move list */}
      <div className="bg-slate-800/40 border border-slate-700/40 rounded-xl px-3 py-2 max-h-40 overflow-y-auto move-list">
        <div className="flex flex-wrap gap-0.5">
          {movesSan.map((san, i) => {
            const isWhiteMove = i % 2 === 0;
            const isCurrent = currentIndex === i + 1;
            const isMistake = mistakeIndices.has(i);
            return (
              <span key={i} className="inline-flex items-center">
                {isWhiteMove && (
                  <span className="text-slate-600 text-xs mr-1 font-mono">
                    {Math.floor(i / 2) + 1}.
                  </span>
                )}
                <button
                  onClick={() => onIndexChange(i + 1)}
                  className={[
                    "text-xs px-1 py-0.5 rounded font-mono transition-colors",
                    isCurrent ? "bg-amber-500 text-gray-900 font-semibold" : "",
                    isMistake && !isCurrent ? "text-red-400 bg-red-400/10" : "",
                    !isCurrent && !isMistake ? "text-slate-400 hover:text-slate-200" : "",
                  ].join(" ")}
                >
                  {san}
                </button>
              </span>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function NavBtn({
  icon: Icon,
  disabled,
  onClick,
  title,
}: {
  icon: React.ElementType;
  disabled: boolean;
  onClick: () => void;
  title: string;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={title}
      className="p-1.5 rounded-lg hover:bg-slate-700 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
    >
      <Icon size={15} className="text-slate-300" />
    </button>
  );
}
