"use client";

import Link from "next/link";
import { ShieldCheck, ShieldAlert } from "lucide-react";
import { ResumeDiff } from "@/components/resume-diff";
import { Card, Loading, Notice, PageHeader, SkillChips } from "@/components/ui/bits";
import { Button } from "@/components/ui/button";
import { API, useApi, useProfileId } from "@/lib/api";
import type { Job, TailorResponse } from "@/lib/types";

export default function TailorPage({ params }: { params: { jobId: string } }) {
  const id = useProfileId();
  const base = id && `/api/profiles/${id}/jobs/${params.jobId}`;
  const job = useApi<Job>(base);
  const tailor = useApi<TailorResponse>(base && `${base}/tailor`);

  if (tailor.loading) return <Loading label="Loading tailored resume" />;
  if (tailor.error || !tailor.data)
    return (
      <Notice
        title="No tailored resume for this job yet"
        action={<Button asChild><Link href={`/jobs/${params.jobId}`}>Go to the job and tailor it</Link></Button>}
      >
        A tailored resume is rebuilt whenever your profile changes, so an older one is not shown.
      </Notice>
    );

  const { result, original } = tailor.data;
  const ok = result.status === "tailored";
  const findings = result.validation?.findings ?? [];
  const url = `${API}${base}/tailor`;

  return (
    <>
      <PageHeader title="Tailored resume" lead={job.data ? `${job.data.title} at ${job.data.company}` : undefined}>
        <div className="flex flex-wrap gap-3">
          <Button asChild>
            <a href={`${url}/pdf`}>Download PDF</a>
          </Button>
          <Button asChild variant="secondary">
            <a href={`${url}/html`} target="_blank" rel="noreferrer">
              Open the print view
            </a>
          </Button>
        </div>
      </PageHeader>

      <Card className="mb-5 flex gap-4">
        {ok ? (
          <ShieldCheck className="mt-0.5 shrink-0 text-strong" aria-hidden />
        ) : (
          <ShieldAlert className="mt-0.5 shrink-0 text-stretch" aria-hidden />
        )}
        <div>
          <h2 className="font-semibold">
            {ok ? `Fact-checked: ${findings.length} claims, none unsupported` : "Your original resume, unchanged"}
          </h2>
          <p className="mt-1 leading-relaxed text-muted">
            {ok
              ? `A separate model compared every claim with your profile${result.attempts > 1 ? " and one rewrite was needed" : ""}. Employers, dates and education are copied from your profile, not written by the model.`
              : result.reason}
          </p>
        </div>
      </Card>

      <ResumeDiff original={original} tailored={result.resume} />

      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <Card>
          <h2 className="text-lg font-semibold">Keywords from the posting</h2>
          <h3 className="mb-2 mt-3 text-sm font-medium text-muted">Covered</h3>
          <SkillChips skills={result.resume.keywords_covered} variant="matched" />
          <h3 className="mb-2 mt-4 text-sm font-medium text-muted">Left out because your profile has no evidence</h3>
          <SkillChips skills={result.resume.keywords_not_covered} variant="missing" />
        </Card>
        <Card>
          <h2 className="text-lg font-semibold">Preview</h2>
          <p className="mt-1 text-sm text-muted">The same layout the PDF uses: one page, US Letter.</p>
          {/* Fixed height reserves the space, so the page does not jump when the frame loads. */}
          <iframe
            src={`${url}/html`}
            title="Tailored resume preview"
            className="mt-3 h-[520px] w-full rounded-lg border border-line"
          />
        </Card>
      </div>
    </>
  );
}
