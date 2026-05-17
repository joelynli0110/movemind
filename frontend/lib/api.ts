import type { AnalysisResponse, Language } from "./types";

const BASE = "/api";

export async function submitPGN(
  pgn: string,
  language: Language = "en",
  playerName?: string,
  playerElo?: number
): Promise<string> {
  const form = new FormData();
  form.append("pgn", new Blob([pgn], { type: "text/plain" }), "game.pgn");
  form.append("language", language);
  if (playerName?.trim()) form.append("player_name", playerName.trim());
  if (playerElo) form.append("player_elo", String(playerElo));

  const res = await fetch(`${BASE}/analyze`, { method: "POST", body: form });
  if (!res.ok) throw new Error(`Upload failed: ${res.statusText}`);
  const data = await res.json();
  return data.game_id as string;
}

export async function pollGame(
  gameId: string,
  options?: { signal?: AbortSignal }
): Promise<AnalysisResponse> {
  const res = await fetch(`${BASE}/game/${gameId}`, { signal: options?.signal });
  if (!res.ok) throw new Error(`Poll failed: ${res.statusText}`);
  return res.json() as Promise<AnalysisResponse>;
}
