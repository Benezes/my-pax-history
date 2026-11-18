import type { Game, MetaResponse, SaveRow, WhatIfResult } from "./types";

function localizeRaw(message: string) {
  const lower = message.toLowerCase();
  if (lower.includes("at most") && lower.includes("12000")) {
    return "O texto da ação pode ter no máximo 12000 caracteres.";
  }
  if (lower.includes("at most") && lower.includes("4000")) {
    return "O texto é longo demais. Reduza um pouco e tente de novo.";
  }
  if (lower.includes("at least")) {
    return "Escreva um pouco mais para o assessor entender a ação.";
  }
  if (lower.startsWith("string should")) {
    return "Há um problema no texto enviado. Revise e tente de novo.";
  }
  return message;
}

async function parseError(response: Response): Promise<string> {
  try {
    const data = await response.json();
    if (typeof data.detail === "string") return localizeRaw(data.detail);
    if (Array.isArray(data.detail)) {
      return data.detail
        .map((item: { msg?: string }) => localizeRaw(item.msg || ""))
        .filter(Boolean)
        .join(" ");
    }
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
  listGeminiModels: (apiKey?: string) =>
    request<{ models: string[] }>("/api/gemini/models", {
      method: "POST",
      body: JSON.stringify({ api_key: apiKey || undefined }),
    }),
};
