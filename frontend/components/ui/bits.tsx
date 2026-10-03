"use client";

import { motion } from "framer-motion";
import { Check, Copy } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import type { Component } from "@/lib/types";
import { cn } from "@/lib/utils";

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("card p-5 sm:p-6", className)} {...props} />;
}

export function PageHeader({ title, lead, children }: { title: string; lead?: string; children?: React.ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold sm:text-3xl">{title}</h1>
        {lead && <p className="mt-1.5 max-w-2xl text-muted">{lead}</p>}
      </div>
      {children}
    </div>
  );
}

/** Placeholder with the height of what will replace it, so loading causes no layout shift. */
export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton", className)} aria-hidden />;
}

export function Loading({ rows = 3, label = "Loading" }: { rows?: number; label?: string }) {
  return (
    <div className="grid gap-4" role="status" aria-label={label}>
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className="h-28 w-full rounded-card" />
      ))}
    </div>
  );
}

/** An empty or failed screen says what happened and what to do next. */
export function Notice({ title, children, action }: { title: string; children?: React.ReactNode; action?: React.ReactNode }) {
  return (
    <Card className="max-w-2xl">
      <h2 className="text-lg font-semibold">{title}</h2>
      {children && <div className="mt-2 leading-relaxed text-muted">{children}</div>}
      {action && <div className="mt-4">{action}</div>}
    </Card>
  );
}

/** Skill chips that stagger in 40 ms apart. Matched skills are filled, missing outlined. */
export function SkillChips({ skills, variant }: { skills: string[]; variant: "matched" | "missing" | "plain" }) {
  return (
    <ul className="flex flex-wrap gap-2">
      {skills.map((skill, i) => (
        <motion.li
          key={skill + i}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.24, delay: i * 0.04, ease: "easeOut" }}
          className={cn(
            "rounded-full px-3 py-1 text-sm",
            variant === "matched" && "bg-surface-2 font-medium text-strong",
            variant === "missing" && "border border-dashed border-line-strong text-muted",
            variant === "plain" && "border border-line text-fg",
          )}
        >
          {skill}
        </motion.li>
      ))}
    </ul>
  );
}

/** One scored component as a labelled bar: "17 / 25" and the reason. */
export function ComponentBars({ components }: { components: Component[] }) {
  return (
    <ul className="grid gap-4">
      {components.map((c) => (
        <li key={c.name}>
          <div className="flex items-baseline justify-between gap-3">
            <span className="font-medium first-letter:uppercase">{c.name}</span>
            <span className="num text-sm text-muted">
              {c.score} / {c.max}
            </span>
          </div>
          <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-surface-2" aria-hidden>
            <motion.div
              className="h-full origin-left rounded-full bg-accent"
              initial={{ scaleX: 0 }}
              animate={{ scaleX: c.max ? c.score / c.max : 0 }}
              transition={{ duration: 0.6, ease: "easeOut" }}
            />
          </div>
          <p className="mt-1.5 text-sm leading-relaxed text-muted">{c.why}</p>
        </li>
      ))}
    </ul>
  );
}

export function CopyButton({ text, label = "Copy" }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <Button
      variant="secondary"
      size="sm"
      onClick={async () => {
        await navigator.clipboard.writeText(text);
        setCopied(true);
        toast.success("Copied");
        setTimeout(() => setCopied(false), 1500);
      }}
    >
      {copied ? <Check size={15} aria-hidden /> : <Copy size={15} aria-hidden />}
      {copied ? "Copied" : label}
    </Button>
  );
}

export const inputClass =
  "w-full rounded-[10px] border border-line-strong bg-surface px-3.5 py-2.5 text-fg placeholder:text-muted";
