"use client";

import { motion } from "framer-motion";
import { Check, RotateCw, X } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { API, api, setProfileId } from "@/lib/api";
import type { RunEvent } from "@/lib/types";
import { cn } from "@/lib/utils";

const AGENTS: [string, string][] = [
  ["resume_analyzer", "Resume analyzer"],
  ["job_discovery", "Job discovery"],
  ["fit_scorer", "Fit scorer"],
  ["resume_tailor", "Resume tailor"],
  ["linkedin_optimizer", "LinkedIn optimizer"],
  ["career_coach", "Career coach"],
];

type State = "pending" | "running" | "done" | "failed";
const RUN_KEY = "careerpilot.run";

export function rememberRun(runId: string) {
  localStorage.setItem(RUN_KEY, runId);
}
export function lastRun(): string | null {
  return typeof window === "undefined" ? null : localStorage.getItem(RUN_KEY);
}

/** Live progress of one run, read from Server-Sent Events. Each agent goes
 *  pending -> running -> done or failed; a failed agent can be retried on its own. */
export function AgentStepper({ runId, onDone }: { runId: string; onDone?: (profileId: string | null) => void }) {
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [finished, setFinished] = useState(false);
  const [profileId, setProfile] = useState<string | null>(null);
  const [lost, setLost] = useState(false);

  useEffect(() => {
    setEvents([]);
    setFinished(false);
    setLost(false);
    // EventSource reconnects by itself and sends Last-Event-ID, so nothing is missed.
    const source = new EventSource(`${API}/api/runs/${runId}/stream`);
    source.addEventListener("progress", (e) => {
      const event = JSON.parse((e as MessageEvent).data) as RunEvent;
      setEvents((all) => [...all, event]);
      if (event.status === "succeeded") toast.success(`${name(event.agent)}: ${event.detail}`);
      if (event.status === "failed") toast.error(`${name(event.agent)}: ${event.detail}`);
    });
    source.addEventListener("done", (e) => {
      const id = JSON.parse((e as MessageEvent).data).profile_id as string | null;
      source.close();
      setFinished(true);
      setProfile(id);
      if (id) setProfileId(id);
      onDone?.(id);
    });
    source.onerror = () => {
      // A run the server no longer knows (it restarted) answers 404 and never recovers.
      if (source.readyState === EventSource.CLOSED) setLost(true);
    };
    return () => source.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId]);

  const state: Record<string, State> = {};
  const detail: Record<string, string> = {};
  for (const e of events) {
    state[e.agent] = e.status === "started" ? "running" : e.status === "succeeded" ? "done" : "failed";
    detail[e.agent] = e.detail;
  }

  async function retry(agent: string) {
    if (!profileId) return toast.error("Upload the resume again to retry this step.");
    const form = new FormData();
    form.set("profile_id", profileId);
    form.append("agents", agent);
    try {
      const { run_id } = await api<{ run_id: string }>("/api/runs", { method: "POST", body: form });
      rememberRun(run_id);
      window.location.reload();
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  if (lost)
    return <p className="text-muted">This run is no longer on the server. Start a new one from the Resume page.</p>;

  return (
    <ol className="relative grid gap-1" aria-label="Agent progress" aria-live="polite">
      {AGENTS.map(([id, label], i) => {
        const s: State = state[id] ?? "pending";
        const skipped = s === "pending" && finished;
        return (
          <li key={id} className="relative flex min-h-[60px] gap-4">
            {i < AGENTS.length - 1 && (
              <span className="absolute left-[15px] top-9 h-[calc(100%-28px)] w-px bg-line-strong" aria-hidden />
            )}
            <span
              className={cn(
                "relative mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border text-sm",
                s === "pending" && "border-line-strong text-muted",
                s === "running" && "border-transparent bg-accent text-on-accent",
                s === "done" && "border-transparent bg-surface-2 text-strong",
                s === "failed" && "border-transparent bg-surface-2 text-stretch",
              )}
            >
              {s === "running" && (
                <motion.span
                  className="absolute inset-0 rounded-full bg-accent"
                  animate={{ scale: [1, 1.5], opacity: [0.5, 0] }}
                  transition={{ duration: 1.2, repeat: Infinity, ease: "easeOut" }}
                  aria-hidden
                />
              )}
              {s === "done" ? (
                <Check size={16} aria-hidden />
              ) : s === "failed" ? (
                <X size={16} aria-hidden />
              ) : (
                <span className="num relative">{i + 1}</span>
              )}
            </span>
            <div className="min-w-0 flex-1 pb-3">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <span className={cn("font-medium", s === "pending" && "text-muted")}>{label}</span>
                <span className="text-sm text-muted">
                  {s === "running" ? "Running" : s === "done" ? "Done" : s === "failed" ? "Failed" : skipped ? "Not needed" : "Waiting"}
                </span>
                {s === "failed" && finished && (
                  <Button variant="secondary" size="sm" onClick={() => retry(id)}>
                    <RotateCw size={14} aria-hidden />
                    Retry
                  </Button>
                )}
              </div>
              {detail[id] && <p className="mt-0.5 text-sm leading-relaxed text-muted">{detail[id]}</p>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function name(agent: string) {
  return AGENTS.find(([id]) => id === agent)?.[1] ?? agent;
}
