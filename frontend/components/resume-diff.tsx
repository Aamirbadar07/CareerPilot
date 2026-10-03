"use client";

import { useRef } from "react";
import { diffWords, type Part } from "@/lib/diff";
import type { Resume, TailoredBullet } from "@/lib/types";

function Words({ parts, side }: { parts: Part[]; side: "before" | "after" }) {
  return (
    <>
      {parts
        .filter((p) => p.kind === "same" || p.kind === (side === "before" ? "remove" : "add"))
        .map((p, i) =>
          p.kind === "same" ? (
            <span key={i}>{p.text} </span>
          ) : side === "before" ? (
            <del key={i} className="rounded bg-[var(--remove-bg)] px-0.5 decoration-[var(--stretch)]">
              {p.text}{" "}
            </del>
          ) : (
            <ins key={i} className="rounded bg-[var(--add-bg)] px-0.5 no-underline">
              {p.text}{" "}
            </ins>
          ),
        )}
    </>
  );
}

type Row = { heading?: string; before: string; after: string };

function rows(original: Resume, tailored: Resume): Row[] {
  const source = new Map<string, string>();
  for (const group of [...original.experience, ...original.projects])
    for (const b of group.bullets) source.set(b.from_bullet, b.text);

  const out: Row[] = [
    { heading: "Title", before: original.title_line, after: tailored.title_line },
    { heading: "Summary", before: original.summary, after: tailored.summary },
    {
      heading: "Skills",
      before: original.skills.flatMap((g) => g.items).join(", "),
      after: tailored.skills.flatMap((g) => g.items).join(", "),
    },
  ];
  const kept = new Set<string>();
  const add = (heading: string, bullets: TailoredBullet[]) =>
    bullets.forEach((b, i) => {
      kept.add(b.from_bullet);
      out.push({ heading: i === 0 ? heading : undefined, before: source.get(b.from_bullet) ?? "", after: b.text });
    });
  tailored.experience.forEach((e) => add("Experience", e.bullets));
  tailored.projects.forEach((p) => add("Projects", p.bullets));
  const cut = Array.from(source).filter(([id]) => !kept.has(id));
  cut.forEach(([, text], i) => out.push({ heading: i === 0 ? "Left out for this job" : undefined, before: text, after: "" }));
  return out;
}

/** Original and tailored resume side by side, each tailored line next to the line it came
 *  from. The two columns scroll together. */
export function ResumeDiff({ original, tailored }: { original: Resume; tailored: Resume }) {
  const left = useRef<HTMLDivElement>(null);
  const right = useRef<HTMLDivElement>(null);
  const syncing = useRef(false);
  const sync = (from: HTMLDivElement | null, to: HTMLDivElement | null) => {
    if (!from || !to || syncing.current) return;
    syncing.current = true;
    to.scrollTop = from.scrollTop;
    requestAnimationFrame(() => (syncing.current = false));
  };
  const all = rows(original, tailored).map((r) => ({ ...r, parts: diffWords(r.before, r.after) }));

  const column = (side: "before" | "after", ref: React.RefObject<HTMLDivElement>, other: React.RefObject<HTMLDivElement>) => (
    <div>
      <h3 className="mb-2 text-sm font-medium text-muted">{side === "before" ? "Your resume" : "Tailored for this job"}</h3>
      <div
        ref={ref}
        onScroll={() => sync(ref.current, other.current)}
        tabIndex={0}
        aria-label={side === "before" ? "Original resume text" : "Tailored resume text"}
        className="card max-h-[560px] overflow-y-auto p-4"
      >
        {all.map((r, i) => (
          <div key={i} className="mb-3">
            {r.heading && <h4 className="mb-1 font-display text-sm font-semibold text-accent">{r.heading}</h4>}
            {/* min-height keeps a cut or new line level with its partner in the other column */}
            <p className="min-h-[1.6em] leading-relaxed">
              <Words parts={r.parts} side={side} />
            </p>
          </div>
        ))}
      </div>
    </div>
  );

  return (
    <div className="grid gap-4 md:grid-cols-2">
      {column("before", left, right)}
      {column("after", right, left)}
    </div>
  );
}
