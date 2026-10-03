import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export type Band = "Strong" | "Competitive" | "Stretch" | "Poor";

/** CSS variable names for a fit band: `ring` for graphics, `text` for AA-safe text. */
export function bandColor(band: string): { ring: string; text: string } {
  const key = ({ Strong: "strong", Competitive: "competitive", Stretch: "stretch" } as Record<string, string>)[band] ?? "poor";
  return { ring: `var(--${key})`, text: `var(--${key}-fg)` };
}

/** The same thresholds as the backend's band_for, for scores that have no band (ATS). */
export function bandFor(score: number): Band {
  if (score >= 75) return "Strong";
  if (score >= 55) return "Competitive";
  if (score >= 35) return "Stretch";
  return "Poor";
}

export function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}
