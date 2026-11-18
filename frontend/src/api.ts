import type { Game, MetaResponse, SaveRow, WhatIfResult } from "./types";

async function parseError(response: Response): Promise<string> {
  try {
    const data = await response.json();
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) return data.detail.map((item: { msg?: string }) => item.msg).join(" ");
    return "Falha na comunicação com o servidor.";
  } catch {
    return "Falha na comunicação com o servidor.";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json() as Promise<T>;
}

export const api = {
  meta: () => request<MetaResponse>("/api/meta"),
  createGame: (body: {
    difficulty: string;
    provider: string;
    api_key?: string;
    ollama_model?: string;
    gemini_model?: string;
    name?: string;
  }) => request<Game>("/api/games", { method: "POST", body: JSON.stringify(body) }),
  listGames: () => request<{ active: SaveRow[]; saves: SaveRow[] }>("/api/games"),
  getGame: (id: string) => request<Game>(`/api/games/${id}`),
  queueAction: (id: string, text: string) =>
    request<Game>(`/api/games/${id}/actions`, { method: "POST", body: JSON.stringify({ text }) }),
  advance: (id: string, months = 1) =>
    request<Game>(`/api/games/${id}/advance`, { method: "POST", body: JSON.stringify({ months }) }),
  whatIf: (id: string, text: string) =>
    request<WhatIfResult>(`/api/games/${id}/what-if`, { method: "POST", body: JSON.stringify({ text }) }),
  advisor: (id: string, message: string) =>
    request<Game>(`/api/games/${id}/advisor`, { method: "POST", body: JSON.stringify({ message }) }),
  save: (id: string, name: string) =>
    request<{ save: SaveRow }>(`/api/games/${id}/save`, { method: "POST", body: JSON.stringify({ name }) }),
  load: (id: string) => request<Game>(`/api/games/${id}/load`, { method: "POST" }),
  saveSettings: (body: Record<string, string>) =>
    request<MetaResponse["settings"]>("/api/settings", { method: "POST", body: JSON.stringify(body) }),
};
