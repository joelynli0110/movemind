import type { AnalysisResponse } from "./types";

const BASE = "/api";

export async function submitPGN(
  pgn: string,
  playerElo: number,
  playerName?: string
): Promise<string> {
  const form = new FormData();
  form.append("pgn", new Blob([pgn], { type: "text/plain" }), "game.pgn");
  form.append("player_elo", String(playerElo));
  if (playerName) form.append("player_name", playerName);

  const res = await fetch(`${BASE}/analyze`, { method: "POST", body: form });
  if (!res.ok) throw new Error(`Upload failed: ${res.statusText}`);
  const data = await res.json();
  return data.game_id as string;
}

export async function pollGame(gameId: string): Promise<AnalysisResponse> {
  const res = await fetch(`${BASE}/game/${gameId}`);
  if (!res.ok) throw new Error(`Poll failed: ${res.statusText}`);
  return res.json() as Promise<AnalysisResponse>;
}
