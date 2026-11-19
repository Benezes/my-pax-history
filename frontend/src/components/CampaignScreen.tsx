import { useState } from "react";
import { CAMPAIGN_MAX, CAMPAIGN_MIN, CAMPAIGN_PROPOSAL_MAX, CAMPAIGN_PROPOSAL_MIN } from "../limits";
import type { CampaignResult, Game } from "../types";

const MONEY = (n: number) =>
  n.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const PCT = (n: number, digits = 1) =>
  `${n.toLocaleString("pt-BR", { minimumFractionDigits: digits, maximumFractionDigits: digits })}%`;

const EMPTY = ["", "", ""];

function ChamberBlock({
  title,
  chamber,
}: {
  title: string;
  chamber: NonNullable<CampaignResult["chamber"]>;
}) {
  const coalition = chamber.government + chamber.allied;
  return (
    <article className="card">
      <h3>{title}</h3>
      <p>
        Base do governo: <b>{coalition}</b> de {chamber.seats} (
        {PCT((coalition / chamber.seats) * 100, 0)})
      </p>
      <ul className="chamber-list">
        <li>Governo {chamber.government}</li>
        <li>Aliados {chamber.allied}</li>
        <li>Oposição {chamber.opposition}</li>
        <li>Independentes {chamber.independent}</li>
      </ul>
    </article>
  );
}

export default function CampaignScreen({
  game,
  error,
  busy,
  onBack,
  onRun,
  onInaugurate,
}: {
  game: Game;
  error: string;
  busy: boolean;
  onBack: () => void;
  onRun: (proposals: string[]) => Promise<void>;
  onInaugurate: () => void;
}) {
  const campaign = game.campaign;
  const [drafts, setDrafts] = useState<string[]>(EMPTY);

  function setAt(index: number, value: string) {
    setDrafts((current) => current.map((item, i) => (i === index ? value : item)));
  }

  const filled = drafts.map((item) => item.trim()).filter(Boolean);
  const tooShort = filled.some((item) => item.length < CAMPAIGN_PROPOSAL_MIN);
  const tooLong = drafts.some((item) => item.length > CAMPAIGN_PROPOSAL_MAX);
  const countBad = filled.length < CAMPAIGN_MIN || filled.length > CAMPAIGN_MAX;

  if (campaign) {
    return (
      <div className="screen">
        <div className="setup">
          <button className="btn ghost" onClick={onBack}>
            ← Sair
          </button>
          <div className="kicker">Mandato das urnas · 2026</div>
          <h1>Vitória nas urnas</h1>
          <p className="muted">{campaign.narrative}</p>
          {error && <div className="banner">{error}</div>}
          <div className="row" style={{ justifyContent: "flex-start", margin: "12px 0 8px" }}>
            <button className="btn primary" onClick={onInaugurate}>
              Tomar posse
            </button>
          </div>
          <div className="cards">
            <article className="card active">
              <h3>{campaign.runoff ? "Segundo turno" : "Primeiro turno"}</h3>
              <p>
                Você {PCT(campaign.winner_share, 1)} · adversário {PCT(campaign.opponent_share, 1)}
              </p>
              <p>
                Margem de <b>{MONEY(campaign.margin_pp)} p.p.</b>
                {campaign.runoff
                  ? ` · 1º turno ${PCT(campaign.first_round_share, 1)}`
                  : " · vitória já no primeiro turno"}
              </p>
              <p className="muted">Comparecimento {PCT(campaign.turnout, 1)}</p>
            </article>
            <article className="card">
              <h3>Lua de mel</h3>
              <p>
                A posse começa com mandato das urnas: ações alinhadas à campanha custam menos capital
                político e passam com mais facilidade no Congresso, sobretudo no primeiro ano.
              </p>
            </article>
          </div>
          <h3>Congresso eleito</h3>
          <p className="muted">
            Apoio da coalizão {PCT(campaign.coalition_support, 0)}. Não há supermaioria automática.
          </p>
          <div className="cards">
            {campaign.chamber && <ChamberBlock title="Câmara" chamber={campaign.chamber} />}
            {campaign.senate && <ChamberBlock title="Senado" chamber={campaign.senate} />}
          </div>
          <h3>Peso das propostas no mandato</h3>
          <div className="mandate-list">
            {campaign.proposals.map((item) => (
              <article key={item.id} className="queued open">
                <p className="full">{item.text}</p>
                <div className="mandate-bar">
                  <i style={{ width: `${Math.max(8, item.weight * 100)}%` }} />
                </div>
                <p className="muted">
                  Peso {PCT(item.weight * 100, 0)} · {item.summary}
                </p>
              </article>
            ))}
          </div>
          <div className="row" style={{ justifyContent: "flex-start", marginTop: 24 }}>
            <button className="btn primary" onClick={onInaugurate}>
              Tomar posse
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="screen">
        <div className="setup">
          <button className="btn ghost" onClick={onBack}>
            ← Voltar
          </button>
          <div className="kicker">Eleição de 2026</div>
          <h1>Campanha presidencial</h1>
        <p className="muted">
          Escreva de {CAMPAIGN_MIN} a {CAMPAIGN_MAX} propostas centrais. O motor simula a urna e o
          Congresso; a IA só classifica a plataforma. Depois da posse, cumprir essas promessas fica
          mais barato em capital político — sobretudo no primeiro ano.
        </p>
        {error && <div className="banner">{error}</div>}
        {drafts.map((value, index) => (
          <label className="field" key={index}>
            Proposta {index + 1}
            <textarea
              value={value}
              maxLength={CAMPAIGN_PROPOSAL_MAX + 40}
              onChange={(e) => setAt(index, e.target.value)}
              placeholder={
                index === 0
                  ? "Ex.: Reforma tributária gradual, unificando tributos sobre consumo."
                  : "Outra proposta da campanha..."
              }
            />
            <span className={`counter ${value.length > CAMPAIGN_PROPOSAL_MAX ? "over" : ""}`}>
              {value.length} / {CAMPAIGN_PROPOSAL_MAX}
            </span>
          </label>
        ))}
        <div className="row" style={{ justifyContent: "flex-start" }}>
          <button
            className="btn"
            type="button"
            disabled={drafts.length >= CAMPAIGN_MAX}
            onClick={() => setDrafts((current) => [...current, ""])}
          >
            Acrescentar proposta
          </button>
          {drafts.length > CAMPAIGN_MIN && (
            <button
              className="btn ghost"
              type="button"
              onClick={() => setDrafts((current) => current.slice(0, -1))}
            >
              Remover última
            </button>
          )}
        </div>
        <button
          className="btn primary"
          disabled={busy || countBad || tooShort || tooLong}
          onClick={() => onRun(filled)}
          style={{ marginTop: 18 }}
        >
          {busy ? "Apurando os votos..." : "Ir às urnas"}
        </button>
      </div>
    </div>
  );
}
