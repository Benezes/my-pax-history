import { useState } from "react";

export default function PendingAction({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  const long = text.length > 96;
  return (
    <article className={`queued ${open ? "open" : ""}`}>
      <p className={open || !long ? "full" : "clamp"} title={long && !open ? text : undefined}>
        {text}
      </p>
      {long && (
        <button
          type="button"
          className="linkish"
          aria-expanded={open}
          onClick={() => setOpen((value) => !value)}
        >
          {open ? "Recolher" : "Ver texto completo"}
        </button>
      )}
    </article>
  );
}
