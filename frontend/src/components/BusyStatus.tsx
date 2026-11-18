export type AiKind = "whatif" | "advance" | "advisor";

const ADVANCE_STEPS = [
  "Simulando o mês… a IA pode levar até 2 minutos.",
  "Interpretando a ação e o Congresso…",
  "Ouvindo reações dos agentes…",
  "Atualizando indicadores e o mundo…",
  "Redigindo o relatório mensal…",
];

export function formatElapsed(seconds: number) {
  if (seconds < 60) return `${seconds} s`;
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return `${minutes} min ${rest.toString().padStart(2, "0")} s`;
}

export function jobCopy(kind: AiKind, months: number, stepIndex: number) {
  if (kind === "whatif") {
    return {
      title: "E se?",
      body: "Simulando a ação… a IA pode levar até 2 minutos.",
    };
  }
  if (kind === "advisor") {
    return {
      title: "Assessor",
      body: "Consultando o assessor… a IA pode levar até 2 minutos.",
    };
  }
  const prefix = months > 1 ? `Simulando ${months} meses. ` : "";
  return {
    title: months > 1 ? `Avançar ${months} meses` : "Avançar 1 mês",
    body: prefix + ADVANCE_STEPS[stepIndex % ADVANCE_STEPS.length],
  };
}

export default function BusyStatus({
  kind,
  months,
  elapsed,
  stepIndex,
}: {
  kind: AiKind;
  months: number;
  elapsed: number;
  stepIndex: number;
}) {
  const copy = jobCopy(kind, months, stepIndex);
  return (
    <div className="wait" role="status" aria-live="polite" data-ai-job={kind}>
      <span className="spinner" aria-hidden="true" />
      <div>
        <strong>{copy.title}</strong>
        <p>{copy.body}</p>
        <p className="muted">Decorrido: {formatElapsed(elapsed)}</p>
      </div>
    </div>
  );
}
