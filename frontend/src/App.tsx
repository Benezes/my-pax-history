import { FormEvent, useEffect, useMemo, useState } from "react";
import { api } from "./api";
import BusyStatus, { type AiKind } from "./components/BusyStatus";
import CampaignScreen from "./components/CampaignScreen";
import GlobeView from "./components/GlobeView";
import PendingAction from "./components/PendingAction";
import { ACTION_MAX, ACTION_MIN, ADVISOR_MAX } from "./limits";
import type { Game, MetaResponse, SaveRow, View, WhatIfResult } from "./types";

const GEMINI_KEY_STORAGE = "presidencia.geminiApiKey";

const MONEY = (n: number) =>
  n.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const NUM = (n: number, digits = 1) =>
  n.toLocaleString("pt-BR", { minimumFractionDigits: digits, maximumFractionDigits: digits });
const PCT = (n: number, digits = 1) => `${NUM(n, digits)}%`;

function readGeminiKey() {
  try {
    return localStorage.getItem(GEMINI_KEY_STORAGE) || "";
  } catch {
    return "";
  }
}

function writeGeminiKey(value: string) {
  try {
    if (value) localStorage.setItem(GEMINI_KEY_STORAGE, value);
    else localStorage.removeItem(GEMINI_KEY_STORAGE);
  } catch {
    return;
  }
}

function ModelNote({ name }: { name?: string | null }) {
  if (!name) return null;
  return <p className="llm-note">Respondido por {name}</p>;
}

function Toast({ message, onClose }: { message: string; onClose: () => void }) {
  if (!message) return null;
  return (
    <div className="toast" role="alert">
      <p>{message}</p>
      <button type="button" className="linkish" onClick={onClose} aria-label="Fechar aviso">
        Fechar
      </button>
    </div>
  );
}

function playView(game: Game): View {
  if (game.campaign_pending && !game.campaign) return "campaign";
  return "game";
}

function formatIndicator(id: string, value: number) {
  if (id === "public_debt_gdp") return `${NUM(value)}% PIB`;
  if (id === "crime_index") return NUM(value, 0);
  if (["selic", "inflation", "unemployment", "gdp_growth", "poverty", "approval"].includes(id)) {
    return PCT(value);
  }
  return NUM(value);
}

export default function App() {
  const [view, setView] = useState<View>("title");
  const [meta, setMeta] = useState<MetaResponse | null>(null);
  const [game, setGame] = useState<Game | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.meta().then(setMeta).catch((err: Error) => setError(err.message));
  }, []);

  if (view === "new") {
    return (
      <NewGame
        meta={meta}
        error={error}
        busy={busy}
        onBack={() => setView("title")}
        onCreate={async (payload) => {
          setBusy(true);
          setError("");
          try {
            const created = await api.createGame(payload);
            setGame(created);
            setView(playView(created));
          } catch (err) {
            setError((err as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      />
    );
  }
  if (view === "load") {
    return (
      <LoadGame
        onBack={() => setView("title")}
        onOpen={async (id) => {
          setBusy(true);
          setError("");
          try {
            const loaded = id.includes("-save-") ? await api.load(id) : await api.getGame(id);
            setGame(loaded);
            setView(playView(loaded));
          } catch (err) {
            setError((err as Error).message);
          } finally {
            setBusy(false);
          }
        }}
        error={error}
      />
    );
  }
  if (view === "settings") {
    return (
      <SettingsScreen
        meta={meta}
        error={error}
        busy={busy}
        onBack={() => setView(game ? playView(game) : "title")}
        onSaved={async () => {
          try {
            setMeta(await api.meta());
          } catch {
            return;
          }
          setError("");
        }}
        setBusy={setBusy}
        setError={setError}
      />
    );
  }
  if (game && (view === "campaign" || (game.campaign_pending && !game.campaign))) {
    return (
      <CampaignScreen
        game={game}
        error={error}
        busy={busy}
        onBack={() => {
          setGame(null);
          setView("title");
        }}
        onRun={async (proposals) => {
          setBusy(true);
          setError("");
          try {
            setGame(await api.runCampaign(game.id, proposals));
            setView("campaign");
          } catch (err) {
            setError((err as Error).message);
          } finally {
            setBusy(false);
          }
        }}
        onInaugurate={() => setView("game")}
      />
    );
  }
  if (view === "game" && game) {
    return (
      <GameScreen
        game={game}
        setGame={setGame}
        error={error}
        setError={setError}
        busy={busy}
        setBusy={setBusy}
        onSettings={() => setView("settings")}
        onExit={() => {
          setGame(null);
          setView("title");
        }}
      />
    );
  }
  return (
    <div className="screen">
      <div className="hero">
        <div className="kicker">Janeiro de 2027</div>
        <h1>Simulador de Presidência do Brasil</h1>
        <p>
          A partida começa na campanha de 2026. Escreva 3 a 5 propostas, dispute a urna e só então
          tome posse. No governo, decisões em linguagem natural gastam espaço fiscal e capital
          político — cumprir o mandato das urnas fica mais barato no primeiro ano.
        </p>
        {error && <div className="banner">{error}</div>}
        <div className="row">
          <button className="btn primary" onClick={() => setView("new")}>
            Nova partida
          </button>
          <button className="btn" onClick={() => setView("load")}>
            Carregar
          </button>
          <button className="btn" onClick={() => setView("settings")}>
            Configurações
          </button>
        </div>
      </div>
    </div>
  );
}

function NewGame({
  meta,
  error,
  busy,
  onBack,
  onCreate,
}: {
  meta: MetaResponse | null;
  error: string;
  busy: boolean;
  onBack: () => void;
  onCreate: (payload: {
    difficulty: string;
    provider: string;
    api_key?: string;
    ollama_model?: string;
    name?: string;
  }) => Promise<void>;
}) {
  const [provider, setProvider] = useState(meta?.settings.default_provider || "mock");
  const [difficulty, setDifficulty] = useState("medio");
  const [apiKey, setApiKey] = useState(() => readGeminiKey());
  const [ollamaModel, setOllamaModel] = useState(meta?.settings.ollama_model || "llama3.2");
  const [name, setName] = useState("Governo 2027");

  useEffect(() => {
    if (meta?.settings.default_provider) setProvider(meta.settings.default_provider);
    if (meta?.settings.ollama_model) setOllamaModel(meta.settings.ollama_model);
  }, [meta]);

  return (
    <div className="screen">
      <div className="setup">
        <button className="btn ghost" onClick={onBack}>
          ← Voltar
        </button>
        <div className="kicker">Configuração da partida</div>
        <h1>Preparar a campanha</h1>
        <p className="muted">
          Depois desta tela você escreve as propostas e vai às urnas. O motor aplica as regras; a IA
          só classifica a plataforma e escreve a narrativa. O modo offline funciona sem nenhum modelo.
        </p>
        {error && <div className="banner">{error}</div>}
        <h3>Provedor de IA</h3>
        <div className="cards">
          {(meta?.providers || []).map((item) => (
            <button
              key={item.id}
              className={`card ${provider === item.id ? "active" : ""}`}
              onClick={() => setProvider(item.id)}
            >
              <h3>{item.label}</h3>
              {item.status?.ok ? (
                <div className="ok">Disponível</div>
              ) : (
                <div className="warn">{item.status?.message || "Verifique a configuração."}</div>
              )}
            </button>
          ))}
        </div>
        {provider === "gemini" && (
          <label className="field">
            Chave Gemini (armazenada só neste computador)
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={meta?.settings.gemini_api_key_set ? "Chave já configurada" : "AIza..."}
            />
          </label>
        )}
        {provider === "ollama" && (
          <label className="field">
            Modelo Ollama
            <input value={ollamaModel} onChange={(e) => setOllamaModel(e.target.value)} />
          </label>
        )}
        <h3>Dificuldade</h3>
        <div className="cards">
          {(meta?.difficulties || []).map((item) => (
            <button
              key={item.id}
              className={`card ${difficulty === item.id ? "active" : ""}`}
              onClick={() => setDifficulty(item.id)}
            >
              <h3>{item.label}</h3>
              <p>{item.blurb}</p>
            </button>
          ))}
        </div>
        <label className="field">
          Nome da partida
          <input value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <button
          className="btn primary"
          disabled={busy}
          onClick={() => {
            if (apiKey.trim()) writeGeminiKey(apiKey.trim());
            onCreate({
              difficulty,
              provider,
              api_key: apiKey || undefined,
              ollama_model: provider === "ollama" ? ollamaModel : undefined,
              name,
            });
          }}
        >
          {busy ? "Abrindo a campanha..." : "Ir para a campanha"}
        </button>
      </div>
    </div>
  );
}

function LoadGame({
  onBack,
  onOpen,
  error,
}: {
  onBack: () => void;
  onOpen: (id: string) => Promise<void>;
  error: string;
}) {
  const [rows, setRows] = useState<{ active: SaveRow[]; saves: SaveRow[] }>({ active: [], saves: [] });
  useEffect(() => {
    api.listGames().then(setRows).catch(() => undefined);
  }, []);
  return (
    <div className="screen">
      <div className="setup">
        <button className="btn ghost" onClick={onBack}>
          ← Voltar
        </button>
        <h1>Carregar partida</h1>
        {error && <div className="banner">{error}</div>}
        <h3>Em andamento</h3>
        <div className="cards">
          {rows.active.map((row) => (
            <button key={row.id} className="card" onClick={() => onOpen(row.id)}>
              <h3>{row.name}</h3>
              <p>{new Date(row.updated_at).toLocaleString("pt-BR")}</p>
            </button>
          ))}
          {rows.active.length === 0 && <p className="muted">Nenhuma partida ativa.</p>}
        </div>
        <h3>Arquivos salvos</h3>
        <div className="cards">
          {rows.saves.map((row) => (
            <button key={row.id} className="card" onClick={() => onOpen(row.id)}>
              <h3>{row.name}</h3>
              <p>{new Date(row.updated_at).toLocaleString("pt-BR")}</p>
            </button>
          ))}
          {rows.saves.length === 0 && <p className="muted">Nenhum save nomeado.</p>}
        </div>
      </div>
    </div>
  );
}

function GameScreen({
  game,
  setGame,
  error,
  setError,
  busy,
  setBusy,
  onSettings,
  onExit,
}: {
  game: Game;
  setGame: (g: Game) => void;
  error: string;
  setError: (s: string) => void;
  busy: boolean;
  setBusy: (b: boolean) => void;
  onSettings: () => void;
  onExit: () => void;
}) {
  const [tab, setTab] = useState<"report" | "history" | "advisor">("report");
  const [pane, setPane] = useState<"map" | "stats" | "intel">("map");
  const [compact, setCompact] = useState(false);
  const [draft, setDraft] = useState("");
  const [whatIf, setWhatIf] = useState<WhatIfResult | null>(null);
  const [advice, setAdvice] = useState("");
  const [saveName, setSaveName] = useState("Arquivo 1");
  const [aiJob, setAiJob] = useState<{ kind: AiKind; months: number } | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [stepIndex, setStepIndex] = useState(0);
  const over = game.status !== "playing";
  const aiBusy = Boolean(aiJob);

  useEffect(() => {
    const apply = () => {
      setCompact(window.innerWidth < 1200 || window.innerHeight < 760);
    };
    apply();
    window.addEventListener("resize", apply);
    return () => window.removeEventListener("resize", apply);
  }, []);

  const fiscalPct = Math.min(
    100,
    (game.budget.fiscal_space_brl_bi / game.budget.fiscal_space_annual_cap_brl_bi) * 100
  );
  const keyIndicators = useMemo(
    () =>
      ["approval", "selic", "inflation", "unemployment", "gdp_growth", "public_debt_gdp", "crime_index"].map(
        (id) => game.indicators.find((item) => item.id === id)
      ),
    [game]
  );

  useEffect(() => {
    if (!aiJob) {
      setElapsed(0);
      setStepIndex(0);
      return;
    }
    const tick = window.setInterval(() => setElapsed((value) => value + 1), 1000);
    const rotate =
      aiJob.kind === "advance"
        ? window.setInterval(() => setStepIndex((value) => value + 1), 12000)
        : 0;
    return () => {
      window.clearInterval(tick);
      if (rotate) window.clearInterval(rotate);
    };
  }, [aiJob]);

  async function run<T>(fn: () => Promise<T>) {
    setBusy(true);
    setError("");
    try {
      return await fn();
    } catch (err) {
      setError((err as Error).message);
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function runAi<T>(kind: AiKind, months: number, fn: () => Promise<T>) {
    setAiJob({ kind, months });
    setElapsed(0);
    setStepIndex(0);
    setError("");
    try {
      return await fn();
    } catch (err) {
      setError((err as Error).message);
      return null;
    } finally {
      setAiJob(null);
    }
  }

  function validateActionText() {
    const trimmed = draft.trim();
    if (trimmed.length < ACTION_MIN) {
      setError("Escreva pelo menos 3 caracteres para o assessor entender a ação.");
      return null;
    }
    if (draft.length > ACTION_MAX) {
      setError(`O texto da ação pode ter no máximo ${ACTION_MAX.toLocaleString("pt-BR")} caracteres.`);
      return null;
    }
    return trimmed;
  }

  async function confirmAction() {
    const text = validateActionText();
    if (!text) return;
    const next = await run(() => api.queueAction(game.id, text));
    if (next) {
      setGame(next);
      setDraft("");
      setWhatIf(null);
    }
  }

  async function askWhatIf() {
    const text = validateActionText();
    if (!text) return;
    const result = await runAi("whatif", 1, () => api.whatIf(game.id, text));
    if (result) setWhatIf(result);
  }

  async function advance(months = 1) {
    const next = await runAi("advance", months, () => api.advance(game.id, months));
    if (next) {
      setGame(next);
      setTab("report");
    }
  }

  async function talk(event: FormEvent) {
    event.preventDefault();
    if (advice.trim().length < 2) return;
    if (advice.length > ADVISOR_MAX) {
      setError(`A pergunta pode ter no máximo ${ADVISOR_MAX.toLocaleString("pt-BR")} caracteres.`);
      return;
    }
    const next = await runAi("advisor", 1, () => api.advisor(game.id, advice.trim()));
    if (next) {
      setGame(next);
      setAdvice("");
      setTab("advisor");
    }
  }

  async function save() {
    await run(() => api.save(game.id, saveName || "Save"));
  }

  if (over) {
    return (
      <div className="over">
        <div className="card">
          <div className="kicker">{game.date_label}</div>
          <h1>{game.loss_title || "Fim de governo"}</h1>
          <p>{game.loss_body}</p>
          <p>
            Aprovação final {PCT(game.indicator_map.approval)} · coalizão{" "}
            {PCT(game.congress.coalition_support, 0)}
          </p>
          <div className="row">
            <button className="btn primary" onClick={onExit}>
              Nova partida
            </button>
          </div>
        </div>
      </div>
    );
  }

  const overLimit = draft.length > ACTION_MAX;
  const tooShort = draft.trim().length < ACTION_MIN;

  return (
    <div className={`game ${compact ? "is-compact" : ""}`}>
      <header className="topbar">
        <div className="brand">
          <strong>Presidência da República</strong>
          <span className="muted">
            {game.name} · {game.date_label} · {game.difficulty_label} · {game.provider_label}
          </span>
        </div>
        <div className="resources">
          <div className="meter" title="Espaço fiscal discricionário do Executivo">
            <span>
              <b>Espaço fiscal</b>
              <b>R$ {MONEY(game.budget.fiscal_space_brl_bi)} bi</b>
            </span>
            <div className="bar">
              <i style={{ width: `${fiscalPct}%` }} />
            </div>
          </div>
          <div className="meter">
            <span>
              <b>Capital político</b>
              <b>{NUM(game.political_capital, 0)}/100</b>
            </span>
            <div className="bar pol">
              <i style={{ width: `${Math.min(100, game.political_capital)}%` }} />
            </div>
          </div>
        </div>
        <div className="row top-actions">
          <input
            className="save-name"
            value={saveName}
            onChange={(e) => setSaveName(e.target.value)}
            aria-label="Nome do arquivo"
          />
          <button className="btn" onClick={save} disabled={busy || aiBusy}>
            Salvar
          </button>
          <button className="btn" onClick={onSettings} disabled={busy}>
            Configurações
          </button>
          <button className="btn ghost" onClick={onExit}>
            Sair
          </button>
        </div>
      </header>
      <Toast message={error} onClose={() => setError("")} />
      {compact && (
        <nav className="mobile-nav">
          <button className={pane === "stats" ? "on" : ""} onClick={() => setPane("stats")}>
            Indicadores
          </button>
          <button className={pane === "map" ? "on" : ""} onClick={() => setPane("map")}>
            Mapa
          </button>
          <button className={pane === "intel" ? "on" : ""} onClick={() => setPane("intel")}>
            Dossiê
          </button>
        </nav>
      )}
      <div className="layout" data-pane={compact ? pane : "full"}>
        <aside className="panel stats">
          <div className="kicker">Indicadores</div>
          {keyIndicators.map(
            (item) =>
              item && (
                <div className="ind" key={item.id}>
                  <span>{item.label}</span>
                  <b>{formatIndicator(item.id, item.value)}</b>
                </div>
              )
          )}
          <div className="ind">
            <span>Impeachment</span>
            <b>{NUM(game.impeachment_pressure, 0)}</b>
          </div>
          <div className="ind">
            <span>Risco de golpe</span>
            <b>{NUM(game.coup_risk, 0)}</b>
          </div>
          <h3 style={{ marginTop: 16 }}>Congresso</h3>
          <p className="muted">Apoio da coalizão {PCT(game.congress.coalition_support, 0)}</p>
          <p className="muted">
            Câmara: base {(game.congress.chamber.government || 0) + (game.congress.chamber.allied || 0)}/
            {game.congress.chamber.seats} · governo {game.congress.chamber.government} · aliados{" "}
            {game.congress.chamber.allied} · oposição {game.congress.chamber.opposition}
          </p>
          <p className="muted">
            Senado: base {(game.congress.senate.government || 0) + (game.congress.senate.allied || 0)}/
            {game.congress.senate.seats} · governo {game.congress.senate.government} · aliados{" "}
            {game.congress.senate.allied} · oposição {game.congress.senate.opposition}
          </p>
          {game.campaign?.proposals?.length ? (
            <>
              <h3 style={{ marginTop: 16 }}>Mandato das urnas</h3>
              <ul className="chamber-list">
                {game.campaign.proposals.map((item) => (
                  <li key={item.id}>
                    {item.summary || item.text} ({PCT(item.weight * 100, 0)})
                  </li>
                ))}
              </ul>
            </>
          ) : null}
          <h3 style={{ marginTop: 16 }}>Agentes</h3>
          {game.agents.map((agent) => (
            <div className="agent" key={agent.id}>
              <div className="ind">
                <span>{agent.name}</span>
                <b>{NUM(agent.stance, 0)}</b>
              </div>
              <div className="stance">
                <i
                  style={
                    agent.stance >= 0
                      ? { left: "50%", width: `${agent.stance / 2}%`, background: "#4ea37a" }
                      : { right: "50%", width: `${Math.abs(agent.stance) / 2}%`, background: "#c45c4a" }
                  }
                />
              </div>
            </div>
          ))}
        </aside>
        <section className="map-col">
          <GlobeView countries={game.map_countries} />
        </section>
        <aside className="panel intel">
          <div className="tabs">
            <button className={`tab ${tab === "report" ? "on" : ""}`} onClick={() => setTab("report")}>
              Relatório
            </button>
            <button className={`tab ${tab === "history" ? "on" : ""}`} onClick={() => setTab("history")}>
              Histórico
            </button>
            <button className={`tab ${tab === "advisor" ? "on" : ""}`} onClick={() => setTab("advisor")}>
              Assessor
            </button>
          </div>
          {tab === "report" && (
            <div className="report">
              {game.last_resolved.map((item) => (
                <article key={`${item.title}-${item.execution}`}>
                  <h4>{item.title}</h4>
                  <span className={`tag ${item.execution}`}>
                    {item.execution === "blocked"
                      ? "bloqueada"
                      : item.execution === "rejected" || !item.passed
                        ? "rejeitada"
                        : item.execution === "full"
                          ? "executada"
                          : "parcial"}
                  </span>
                  {item.mandate_applied ? <span className="tag mandate">Mandato das urnas</span> : null}
                  {item.capital_refunded ? (
                    <span className="tag refund">
                      Devolvidos {NUM(item.capital_refunded)} de capital
                    </span>
                  ) : null}
                  <p>{item.reason}</p>
                  {item.mandate_note && !item.reason.includes(item.mandate_note) ? (
                    <p className="muted">{item.mandate_note}</p>
                  ) : null}
                </article>
              ))}
              {game.last_report ? (
                <>
                  <div className="kicker">Relatório — {game.last_report_date_label || game.date_label}</div>
                  <ModelNote name={game.last_llm_model} />
                  <article>
                    <h4>Economia</h4>
                    <p>{game.last_report.economia}</p>
                  </article>
                  <article>
                    <h4>Política</h4>
                    <p>{game.last_report.politica}</p>
                  </article>
                  <article>
                    <h4>Segurança</h4>
                    <p>{game.last_report.seguranca}</p>
                  </article>
                  <article>
                    <h4>Aprovação</h4>
                    <p>{game.last_report.aprovacao}</p>
                  </article>
                  <article>
                    <h4>Relações internacionais</h4>
                    <p>{game.last_report.relacoes_internacionais}</p>
                  </article>
                  <article>
                    <h4>Consequências</h4>
                    <p>{game.last_report.consequencias}</p>
                  </article>
                  <article>
                    <h4>Problemas</h4>
                    <p>{game.last_report.problemas}</p>
                  </article>
                </>
              ) : (
                <p className="muted">Avance o tempo para gerar o primeiro relatório.</p>
              )}
            </div>
          )}
          {tab === "history" && (
            <div className="timeline">
              {[...game.history]
                .slice()
                .sort((a, b) => b.month_index - a.month_index || b.id.localeCompare(a.id))
                .map((item) => (
                  <div className="t-item" key={item.id}>
                    <small>
                      {item.date_label} · {item.kind}
                    </small>
                    <div>
                      <b>{item.title}</b>
                    </div>
                    <div className="muted">{item.body}</div>
                  </div>
                ))}
            </div>
          )}
          {tab === "advisor" && (
            <>
              <div className="chat">
                {game.advisor_log.map((item, index) => (
                  <div
                    key={index}
                    className={`bubble ${item.role === "user" ? "user" : ""} ${item.disagrees ? "disagree" : ""}`}
                  >
                    {item.content}
                    {item.role === "advisor" && item.answered_by ? (
                      <ModelNote name={item.answered_by} />
                    ) : null}
                  </div>
                ))}
              </div>
              {aiJob?.kind === "advisor" && (
                <BusyStatus kind="advisor" months={1} elapsed={elapsed} stepIndex={stepIndex} />
              )}
              <form onSubmit={talk} className="field">
                <input
                  value={advice}
                  onChange={(e) => setAdvice(e.target.value)}
                  maxLength={ADVISOR_MAX}
                  placeholder="Pergunte ao assessor..."
                />
                <button className="btn" disabled={busy || aiBusy}>
                  Enviar
                </button>
              </form>
            </>
          )}
        </aside>
      </div>
      <div className="dock">
        <div className="dock-head">
          <div className="kicker">Campo de ações</div>
          <span className={`counter ${overLimit ? "over" : ""}`}>
            {draft.length.toLocaleString("pt-BR")} / {ACTION_MAX.toLocaleString("pt-BR")}
          </span>
        </div>
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          maxLength={ACTION_MAX + 200}
          placeholder="Ex.: Propor uma reforma tributária gradual e negociar a base do centrão com emendas de infraestrutura no Nordeste."
        />
        {game.pending_actions.length > 0 && (
          <div className="pending">
            {game.pending_actions.map((item) => (
              <PendingAction key={item.id} text={item.text} />
            ))}
          </div>
        )}
        {aiJob && (aiJob.kind !== "advisor" || tab !== "advisor") && (
          <BusyStatus kind={aiJob.kind} months={aiJob.months} elapsed={elapsed} stepIndex={stepIndex} />
        )}
        <div className="row dock-actions">
          <button className="btn" disabled={busy || aiBusy || tooShort || overLimit} onClick={askWhatIf}>
            E se?
          </button>
          <button className="btn primary" disabled={busy || aiBusy || tooShort || overLimit} onClick={confirmAction}>
            Registrar ação
          </button>
          <button className="btn" disabled={busy || aiBusy} onClick={() => advance(1)}>
            Avançar 1 mês
          </button>
          <button className="btn" disabled={busy || aiBusy} onClick={() => advance(3)}>
            Avançar 3 meses
          </button>
        </div>
        {whatIf && <WhatIfPanel result={whatIf} onConfirm={confirmAction} onClose={() => setWhatIf(null)} />}
      </div>
    </div>
  );
}

function SettingsScreen({
  meta,
  error,
  busy,
  onBack,
  onSaved,
  setBusy,
  setError,
}: {
  meta: MetaResponse | null;
  error: string;
  busy: boolean;
  onBack: () => void;
  onSaved: () => Promise<void>;
  setBusy: (b: boolean) => void;
  setError: (s: string) => void;
}) {
  const [defaultProvider, setDefaultProvider] = useState(meta?.settings.default_provider || "mock");
  const [geminiKey, setGeminiKey] = useState(() => readGeminiKey());
  const [geminiModel, setGeminiModel] = useState(meta?.settings.gemini_model || "gemini-flash-latest");
  const [geminiModels, setGeminiModels] = useState<string[]>([]);
  const [ollamaUrl, setOllamaUrl] = useState(meta?.settings.ollama_base_url || "http://127.0.0.1:11434");
  const [ollamaModel, setOllamaModel] = useState(meta?.settings.ollama_model || "llama3.2");
  const [ok, setOk] = useState("");

  useEffect(() => {
    if (!meta) return;
    setDefaultProvider(meta.settings.default_provider || "mock");
    setGeminiModel(meta.settings.gemini_model || "gemini-flash-latest");
    setOllamaUrl(meta.settings.ollama_base_url || "http://127.0.0.1:11434");
    setOllamaModel(meta.settings.ollama_model || "llama3.2");
  }, [meta]);

  useEffect(() => {
    const key = geminiKey.trim();
    if (!key && !meta?.settings.gemini_api_key_set) {
      setGeminiModels([]);
      return;
    }
    api
      .listGeminiModels(key || undefined)
      .then((data) => setGeminiModels(data.models))
      .catch(() => setGeminiModels([]));
  }, [geminiKey, meta]);

  async function save() {
    setBusy(true);
    setError("");
    setOk("");
    try {
      writeGeminiKey(geminiKey.trim());
      const body: Record<string, string> = {
        default_provider: defaultProvider,
        gemini_model: geminiModel.trim(),
        ollama_base_url: ollamaUrl.trim(),
        ollama_model: ollamaModel.trim(),
      };
      if (geminiKey.trim()) body.gemini_api_key = geminiKey.trim();
      await api.saveSettings(body);
      await onSaved();
      setOk("Configurações salvas neste computador.");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="screen">
      <div className="setup">
        <button className="btn ghost" onClick={onBack}>
          ← Voltar
        </button>
        <div className="kicker">Preferências locais</div>
        <h1>Configurações</h1>
        <p className="muted">
          Provedor padrão, modelo e URL do Ollama ficam no SQLite local. A chave Gemini é gravada
          só neste navegador e, se preenchida, também no banco local — nunca no repositório.
        </p>
        {error && <div className="banner">{error}</div>}
        {ok && <div className="ok">{ok}</div>}
        <h3>Provedor padrão</h3>
        <div className="cards">
          {(meta?.providers || []).map((item) => (
            <button
              key={item.id}
              className={`card ${defaultProvider === item.id ? "active" : ""}`}
              onClick={() => setDefaultProvider(item.id)}
            >
              <h3>{item.label}</h3>
              {item.status?.ok ? (
                <div className="ok">Disponível</div>
              ) : (
                <div className="warn">{item.status?.message || "Verifique a configuração."}</div>
              )}
            </button>
          ))}
        </div>
        <label className="field">
          Chave Gemini (somente neste computador)
          <input
            type="password"
            value={geminiKey}
            onChange={(e) => setGeminiKey(e.target.value)}
            placeholder={meta?.settings.gemini_api_key_set ? "Chave já configurada" : "AIza..."}
          />
        </label>
        <label className="field">
          Modelo Gemini
          {geminiModels.length > 0 ? (
            <select value={geminiModel} onChange={(e) => setGeminiModel(e.target.value)}>
              {geminiModels.includes(geminiModel) ? null : (
                <option value={geminiModel}>{geminiModel}</option>
              )}
              {geminiModels.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          ) : (
            <input
              value={geminiModel}
              onChange={(e) => setGeminiModel(e.target.value)}
              placeholder="gemini-flash-latest"
            />
          )}
        </label>
        <label className="field">
          URL do Ollama
          <input value={ollamaUrl} onChange={(e) => setOllamaUrl(e.target.value)} />
        </label>
        <label className="field">
          Modelo Ollama
          <input value={ollamaModel} onChange={(e) => setOllamaModel(e.target.value)} />
        </label>
        <button className="btn primary" disabled={busy} onClick={save}>
          {busy ? "Salvando..." : "Salvar configurações"}
        </button>
      </div>
    </div>
  );
}

function WhatIfPanel({
  result,
  onConfirm,
  onClose,
}: {
  result: WhatIfResult;
  onConfirm: () => void;
  onClose: () => void;
}) {
  return (
    <div className="whatif">
      <div className="kicker">E se?</div>
      <ModelNote name={result.answered_by} />
      <h3>{result.title}</h3>
      <span className={`tag ${result.execution}`}>
        {result.execution === "full"
          ? "cabe no orçamento"
          : result.execution === "partial"
            ? "execução parcial"
            : result.execution === "rejected"
              ? "seria rejeitada"
              : "seria bloqueada"}
      </span>
      {result.mandate_applied ? <span className="tag mandate">Mandato das urnas</span> : null}
      <p>{result.summary}</p>
      <p>
        Custo estimado: <b>R$ {MONEY(result.fiscal_cost_brl_bi)} bi</b> e{" "}
        <b>{NUM(result.political_cost, 0)} de capital político</b>. Disponível: R${" "}
        {MONEY(result.fiscal_available)} bi / {NUM(result.political_available, 0)} cap.
      </p>
      {result.mandate_note ? <p>{result.mandate_note}</p> : null}
      <p>{result.resource_message}</p>
      {result.requires_congress && (
        <p>Requer Congresso. Chance projetada de aprovação: {PCT(result.pass_chance * 100, 0)}.</p>
      )}
      <p className="muted">{result.timing_note}</p>
      {result.likely_effects.length > 0 && (
        <ul>
          {result.likely_effects.map((item) => (
            <li key={item.indicator}>
              {item.label}: {item.immediate_delta ? `${item.immediate_delta > 0 ? "+" : ""}${NUM(item.immediate_delta)} agora` : ""}
              {item.delayed_delta
                ? ` ${item.delayed_delta > 0 ? "+" : ""}${NUM(item.delayed_delta)} em ${item.delay_months} mês(es)`
                : ""}
            </li>
          ))}
        </ul>
      )}
      {result.agent_reactions.length > 0 && (
        <ul>
          {result.agent_reactions.map((item) => (
            <li key={item.agent_id}>
              {item.name} ({item.action_type}) {item.statement}
            </li>
          ))}
        </ul>
      )}
      {result.risks.length > 0 && <p>Riscos: {result.risks.join("; ")}.</p>}
      <p className={result.disagrees ? "banner" : ""}>{result.advisor_commentary}</p>
      <div className="row" style={{ justifyContent: "flex-start" }}>
        <button className="btn primary" onClick={onConfirm}>
          {result.execution === "blocked" ? "Registrar mesmo assim" : "Confirmar ação"}
        </button>
        <button className="btn" onClick={onClose}>
          Editar
        </button>
      </div>
    </div>
  );
}
