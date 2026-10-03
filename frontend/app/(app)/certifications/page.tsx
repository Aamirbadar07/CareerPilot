"use client";

import { BadgeCheck } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";
import { Card, inputClass, Loading, Notice, PageHeader, SkillChips } from "@/components/ui/bits";
import { Button } from "@/components/ui/button";
import { api, SAMPLE, useApi, useProfileId } from "@/lib/api";
import type { Certification, CredentialsResponse, Proposal } from "@/lib/types";

export default function CertificationsPage() {
  const id = useProfileId();
  const { data, loading, reload } = useApi<CredentialsResponse>(id && `/api/profiles/${id}/credentials`);
  const [url, setUrl] = useState("");
  const [statement, setStatement] = useState("");
  const [busy, setBusy] = useState(false);
  const file = useRef<HTMLInputElement>(null);
  const own = id !== null && id !== SAMPLE;
  const base = `/api/profiles/${id}/credentials`;

  async function propose(form: FormData) {
    setBusy(true);
    try {
      await api(base, { method: "POST", body: form });
      toast.success("Read. Check the details below, then confirm.");
      setUrl("");
      setStatement("");
      reload();
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function decide(proposalId: string, confirm: boolean) {
    try {
      await api(`${base}/${proposalId}${confirm ? "/confirm" : ""}`, { method: confirm ? "POST" : "DELETE" });
      toast.success(confirm ? "Added to your profile. Tailored resumes will be rebuilt from it." : "Discarded");
      reload();
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  return (
    <>
      <PageHeader
        title="Certifications"
        lead="Add a new certificate and every later resume, LinkedIn suggestion and coaching plan uses it. Nothing is added until you confirm."
      />

      {own && (
        <Card className="mb-6">
          <h2 className="text-lg font-semibold">Add a certification</h2>
          <div className="mt-4 grid gap-5 md:grid-cols-3">
            <div>
              <h3 className="font-medium">Upload the certificate</h3>
              <p className="mt-1 text-sm text-muted">PDF, DOCX or TXT. Counts as verified if it shows a credential id.</p>
              <input
                ref={file}
                type="file"
                accept=".pdf,.docx,.txt"
                className="sr-only"
                aria-label="Certificate file"
                onChange={(e) => {
                  const chosen = e.target.files?.[0];
                  if (!chosen) return;
                  const form = new FormData();
                  form.set("file", chosen);
                  propose(form);
                }}
              />
              <Button className="mt-3" variant="secondary" size="sm" disabled={busy} onClick={() => file.current?.click()}>
                Choose a file
              </Button>
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const form = new FormData();
                form.set("url", url);
                if (statement) form.set("statement", statement);
                propose(form);
              }}
            >
              <label htmlFor="credential-url" className="font-medium">
                Or paste its link
              </label>
              <p className="mt-1 text-sm text-muted">Credly, Coursera, AWS and similar. The link is recorded, not opened.</p>
              <input
                id="credential-url"
                type="url"
                className={`${inputClass} mt-2`}
                placeholder="https://www.credly.com/badges/..."
                value={url}
                onChange={(e) => setUrl(e.target.value)}
              />
              <Button className="mt-3" variant="secondary" size="sm" disabled={busy || !url}>
                Read this link
              </Button>
            </form>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const form = new FormData();
                form.set("statement", statement);
                propose(form);
              }}
            >
              <label htmlFor="credential-statement" className="font-medium">
                Or describe it
              </label>
              <p className="mt-1 text-sm text-muted">Without a link or id it is recorded as unverified.</p>
              <textarea
                id="credential-statement"
                className={`${inputClass} mt-2 min-h-[72px]`}
                placeholder="AWS Certified AI Practitioner, issued August 2026"
                value={statement}
                onChange={(e) => setStatement(e.target.value)}
              />
              <Button className="mt-3" variant="secondary" size="sm" disabled={busy || statement.trim().length < 10 || !!url}>
                Read this
              </Button>
            </form>
          </div>
        </Card>
      )}

      {loading ? (
        <Loading label="Loading certifications" />
      ) : (
        <div className="grid gap-5">
          {data?.pending.map(({ proposal_id, proposal }) => (
            <Pending key={proposal_id} proposal={proposal} onDecide={(ok) => decide(proposal_id, ok)} />
          ))}

          <div className="grid gap-5 lg:grid-cols-[1.4fr_1fr]">
            <Card>
              <h2 className="text-lg font-semibold">On your profile</h2>
              {data?.certifications.length === 0 && <p className="mt-2 text-muted">No certifications yet.</p>}
              <ul className="mt-4 grid gap-5">
                {data?.certifications.map((c) => <Cert key={c.id} cert={c} />)}
              </ul>
            </Card>
            <Card>
              <h2 className="text-lg font-semibold">History</h2>
              {data?.history.length === 0 ? (
                <p className="mt-2 leading-relaxed text-muted">
                  Each confirmed certification creates a new profile version and is listed here.
                </p>
              ) : (
                <ul className="mt-3 grid gap-2">
                  {data?.history.map((h) => (
                    <li key={h.version} className="flex justify-between gap-3 text-sm">
                      <span>
                        Version <span className="num">{h.version}</span>: {h.change}
                      </span>
                      <span className="num text-muted">{h.at.slice(0, 10)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>
        </div>
      )}
      {!own && !loading && (
        <div className="mt-5">
          <Notice title="Adding certificates needs your own profile">Upload a resume, then add certificates here.</Notice>
        </div>
      )}
    </>
  );
}

function Verified({ verified }: { verified: boolean }) {
  return verified ? (
    <span className="inline-flex items-center gap-1 text-sm font-medium text-strong">
      <BadgeCheck size={15} aria-hidden /> Verified
    </span>
  ) : (
    <span className="text-sm font-medium text-competitive">Unverified</span>
  );
}

function Cert({ cert }: { cert: Certification }) {
  return (
    <li>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="font-medium">{cert.name}</span>
        <Verified verified={cert.verified} />
      </div>
      <p className="text-sm text-muted">
        {[cert.issuer, cert.issued && `issued ${cert.issued}`, cert.expires && `expires ${cert.expires}`]
          .filter(Boolean)
          .join(", ")}
      </p>
      {!cert.verified && (
        <p className="mt-1 text-sm text-muted">Add its credential link or id to verify it.</p>
      )}
      <div className="mt-2">
        <SkillChips skills={cert.skills_covered} variant="plain" />
      </div>
    </li>
  );
}

function Pending({ proposal, onDecide }: { proposal: Proposal; onDecide: (confirm: boolean) => void }) {
  const d = proposal.downstream;
  return (
    <Card className="border-line-strong">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-semibold">Confirm before anything is added</h2>
        <Verified verified={proposal.verified} />
      </div>
      <p className="mt-2 text-[17px] leading-relaxed">{proposal.confirmation_prompt}</p>
      {proposal.needs_review.length > 0 && (
        <p className="mt-3 rounded-lg border border-line-strong px-3 py-2 text-sm leading-relaxed text-competitive">
          Check these before confirming, because the evidence did not show them clearly:{" "}
          {proposal.needs_review.join(", ").replaceAll("_", " ")}.
        </p>
      )}
      <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
        <div>
          <dt className="font-medium">Target roles this supports</dt>
          <dd className="text-muted">{d.roles_strengthened.join(", ") || "None directly"}</dd>
        </div>
        <div>
          <dt className="font-medium">Gaps it closes</dt>
          <dd className="text-muted">{d.gaps_closed.join(", ") || "None of the gaps in your scored jobs"}</dd>
        </div>
        <div>
          <dt className="font-medium">Resumes that will be rebuilt</dt>
          <dd className="text-muted">{d.stale_resumes.join(", ") || "None yet"}</dd>
        </div>
      </dl>
      <div className="mt-5 flex flex-wrap gap-3">
        <Button onClick={() => onDecide(true)}>Add to my profile</Button>
        <Button variant="secondary" onClick={() => onDecide(false)}>
          Discard
        </Button>
        <Button asChild variant="ghost">
          <a href={proposal.linkedin_add_url} target="_blank" rel="noreferrer">
            Add it on LinkedIn too
          </a>
        </Button>
      </div>
    </Card>
  );
}
