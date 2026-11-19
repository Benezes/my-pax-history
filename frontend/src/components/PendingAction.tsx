import { useEffect, useRef, useState } from "react";

export default function PendingAction({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  const [truncated, setTruncated] = useState(false);
  const ref = useRef<HTMLParagraphElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el || open) return;
    const measure = () => setTruncated(el.scrollHeight > el.clientHeight + 2);
    measure();
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(measure);
    observer?.observe(el);
    return () => observer?.disconnect();
  }, [text, open]);

  return (
    <article className={`queued ${open ? "open" : ""}`}>
      <p
        ref={ref}
        className={open ? "full" : "clamp"}
        title={truncated && !open ? text : undefined}
      >
        {text}
      </p>
      {truncated && (
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
