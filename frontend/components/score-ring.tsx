"use client";

import { useEffect, useState } from "react";
import { bandColor, bandFor, prefersReducedMotion } from "@/lib/utils";

const DURATION_MS = 900;

/** An SVG arc that counts from 0 to the score, coloured by band. Space is reserved by the
 *  fixed size, so nothing shifts while it animates. */
export function ScoreRing({
  score,
  band,
  size = 72,
  label,
}: {
  score: number;
  band?: string;
  size?: number;
  label?: string;
}) {
  const [shown, setShown] = useState(0);
  useEffect(() => {
    if (prefersReducedMotion()) return setShown(score);
    const start = performance.now();
    let frame = requestAnimationFrame(function tick(now) {
      const t = Math.min(1, (now - start) / DURATION_MS);
      setShown(Math.round(score * (1 - (1 - t) ** 3))); // ease-out
      if (t < 1) frame = requestAnimationFrame(tick);
    });
    return () => cancelAnimationFrame(frame);
  }, [score]);

  const resolved = band ?? bandFor(score);
  const { ring, text } = bandColor(resolved);
  const stroke = Math.max(5, size / 11);
  const r = (size - stroke) / 2;
  const circumference = 2 * Math.PI * r;
  return (
    <div
      className="relative shrink-0"
      style={{ width: size, height: size }}
      role="img"
      aria-label={`${label ?? "Score"} ${score} out of 100, ${resolved}`}
    >
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--surface-2)" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={ring}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - shown / 100)}
        />
      </svg>
      <span
        className="num absolute inset-0 flex items-center justify-center font-semibold"
        style={{ color: text, fontSize: size * 0.3 }}
        aria-hidden
      >
        {shown}
      </span>
    </div>
  );
}

export function BandBadge({ band }: { band: string }) {
  const { ring, text } = bandColor(band);
  return (
    <span className="inline-flex items-center gap-1.5 text-sm font-medium" style={{ color: text }}>
      <span className="h-2 w-2 rounded-full" style={{ background: ring }} aria-hidden />
      {band}
    </span>
  );
}
