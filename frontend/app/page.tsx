"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { submitPGN } from "@/lib/api";
import { Upload, ChevronRight, Brain, Target, TrendingUp } from "lucide-react";

const SAMPLE_PGN = `[Event "Casual Game"]
[White "You"]
[Black "Opponent"]
[Result "0-1"]

1. e4 e5 2. Nf3 Nc6 3. Bc4 Nf6 4. Ng5 d5 5. exd5 Na5 6. Bb5+ c6
7. dxc6 bxc6 8. Be2 h6 9. Nf3 e4 10. Ne5 Qd4 11. f4 Bc5
12. Rf1 O-O 13. Nc3 Ng4 14. Nxg4 Bxg4 15. Bxg4 Qxf4 0-1`;

export default function HomePage() {
  const router = useRouter();
  const [pgn, setPgn] = useState("");
  const [elo, setElo] = useState(1200);
  const [playerName, setPlayerName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!pgn.trim()) {
      setError("Please paste a PGN or drop a .pgn file.");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const gameId = await submitPGN(pgn, elo, playerName || undefined);
      router.push(`/review/${gameId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
      setLoading(false);
    }
  }

  function handleFileDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) readFile(file);
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) readFile(file);
  }

  function readFile(file: File) {
    const reader = new FileReader();
    reader.onload = (ev) => setPgn(ev.target?.result as string ?? "");
    reader.readAsText(file);
  }

  return (
    <main className="min-h-screen bg-[#0a0e1a] flex flex-col">
      {/* Header */}
      <header className="border-b border-slate-800 px-6 py-4 flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-amber-500 flex items-center justify-center font-bold text-gray-900">
          M
        </div>
        <span className="text-lg font-semibold tracking-tight">MoveMind</span>
        <span className="text-slate-500 text-sm ml-1">AI Chess Coach</span>
      </header>

      {/* Hero */}
      <div className="flex-1 flex flex-col items-center justify-center px-4 py-16">
        <div className="max-w-2xl w-full space-y-8">
          <div className="text-center space-y-3">
            <h1 className="text-4xl font-bold tracking-tight">
              Understand your <span className="text-amber-400">chess mistakes</span>
            </h1>
            <p className="text-slate-400 text-lg">
              Upload a game. Get coach-style explanations for your 3 biggest mistakes.
              Learn the thought process — not just the best move.
            </p>
          </div>

          {/* Feature pills */}
          <div className="flex flex-wrap justify-center gap-3">
            {[
              { icon: Brain, label: "Why not my move?" },
              { icon: Target, label: "How to find it next time" },
              { icon: TrendingUp, label: "Personalized training plan" },
            ].map(({ icon: Icon, label }) => (
              <div
                key={label}
                className="flex items-center gap-2 bg-slate-800/60 border border-slate-700 rounded-full px-4 py-1.5 text-sm text-slate-300"
              >
                <Icon size={14} className="text-amber-400" />
                {label}
              </div>
            ))}
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Drop zone */}
            <div
              onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={handleFileDrop}
              className={`relative border-2 border-dashed rounded-xl p-4 transition-colors ${
                dragging
                  ? "border-amber-400 bg-amber-400/5"
                  : "border-slate-700 hover:border-slate-500"
              }`}
            >
              <textarea
                value={pgn}
                onChange={(e) => setPgn(e.target.value)}
                placeholder={`Paste your PGN here, or drag & drop a .pgn file…\n\nExample:\n${SAMPLE_PGN.split("\n").slice(0, 3).join("\n")}\n…`}
                rows={8}
                className="w-full bg-transparent text-sm text-slate-300 placeholder-slate-600 resize-none outline-none font-mono"
              />
              <label className="absolute bottom-3 right-3 cursor-pointer flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-300 transition-colors">
                <Upload size={12} />
                Upload .pgn
                <input type="file" accept=".pgn,.txt" className="hidden" onChange={handleFileChange} />
              </label>
            </div>

            {/* Options row */}
            <div className="flex gap-3">
              <div className="flex-1">
                <label className="block text-xs text-slate-500 mb-1">Your name in PGN (optional)</label>
                <input
                  type="text"
                  value={playerName}
                  onChange={(e) => setPlayerName(e.target.value)}
                  placeholder="e.g. Magnus"
                  className="w-full bg-slate-800/60 border border-slate-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-amber-500 transition-colors"
                />
              </div>
              <div className="w-36">
                <label className="block text-xs text-slate-500 mb-1">Your Elo rating</label>
                <input
                  type="number"
                  value={elo}
                  onChange={(e) => setElo(Number(e.target.value))}
                  min={400}
                  max={3000}
                  className="w-full bg-slate-800/60 border border-slate-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-amber-500 transition-colors"
                />
              </div>
            </div>

            {error && (
              <p className="text-red-400 text-sm bg-red-400/10 border border-red-400/20 rounded-lg px-3 py-2">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 bg-amber-500 hover:bg-amber-400 disabled:opacity-50 disabled:cursor-not-allowed text-gray-900 font-semibold rounded-xl py-3 transition-colors"
            >
              {loading ? (
                <>
                  <span className="w-4 h-4 border-2 border-gray-900/30 border-t-gray-900 rounded-full animate-spin" />
                  Submitting…
                </>
              ) : (
                <>
                  Analyze my game
                  <ChevronRight size={16} />
                </>
              )}
            </button>

            <p className="text-center text-xs text-slate-600">
              Analysis takes ~30–60 seconds. Requires Stockfish + Anthropic API key on the server.
            </p>
          </form>
        </div>
      </div>
    </main>
  );
}
