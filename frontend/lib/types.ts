// Shapes of the backend's JSON. Kept to the fields the UI reads.

export type Bullet = { id: string; text: string; skills: string[] };
export type Certification = {
  id: string;
  name: string;
  issuer: string | null;
  issued: string | null;
  expires: string | null;
  credential_id: string | null;
  credential_url: string | null;
  skills_covered: string[];
  verified: boolean;
};
export type Preferences = {
  remote_only: boolean;
  locations: string[];
  min_salary: number | null;
  currency: string;
  employment_types: string[];
  exclude_companies: string[];
};
export type Profile = {
  profile_id: string;
  version: number;
  identity: { full_name: string | null; title_line: string | null; location: string | null };
  skills: { name: string; category: string; evidence: string[] }[];
  experience: { id: string; company: string; role: string; bullets: Bullet[] }[];
  projects: { id: string; name: string; bullets: Bullet[] }[];
  certifications: Certification[];
  target_roles: { title: string; seniority: string | null }[];
  preferences: Preferences;
};

export type Component = { name: string; score: number; max: number; why: string };
export type Analysis = {
  ats: { score: number; components: Component[] };
  weak_bullets: { bullet_id: string; problem: string; rewrite: string; needs_from_user: string | null }[];
  missing_keywords: { keyword: string; for_role: string; severity: "high" | "medium" | "low" }[];
  target_roles: { title: string; confidence: number; evidence: string[] }[];
  top_gaps: { gap: string; blocks: string; smallest_action: string }[];
  overall_verdict: string;
};
export type ProfileResponse = {
  profile: Profile;
  analysis: Analysis | null;
  expires_at: string | null;
  is_sample: boolean;
};

export type Fit = {
  score: number;
  band: string;
  dimensions: Component[];
  matched: { skill: string; evidence: string }[];
  missing: { skill: string; type: "blocker" | "learnable"; how_to_close: string }[];
  closable_now: string[];
  resume_angle: string;
  application_priority: number;
  verdict: string;
  capped: boolean;
};
export type Job = {
  id: string;
  title: string;
  company: string;
  location: string | null;
  remote: boolean | null;
  posted: string | null;
  url: string;
  source: string;
  must_have: string[];
  nice_to_have: string[];
  years_required: number | string | null;
  stack: string[];
  employment_type: string | null;
  salary: string | null;
  description_excerpt: string;
  fit: Fit | null;
  tailored?: boolean;
};
export type JobsResponse = {
  jobs: Job[];
  discovery: { queries: { q: string; source: string }[]; dropped: { title: string; company: string; reason: string }[] } | null;
};

export type TailoredBullet = { text: string; from_bullet: string };
export type Resume = {
  title_line: string;
  summary: string;
  skills: { category: string; items: string[] }[];
  experience: { exp_id: string; bullets: TailoredBullet[] }[];
  projects: { proj_id: string; bullets: TailoredBullet[] }[];
  keywords_covered: string[];
  keywords_not_covered: string[];
};
export type TailorResponse = {
  result: {
    status: "tailored" | "untailored";
    resume: Resume;
    validation: { verdict: "pass" | "fail"; findings: { claim: string; status: string; fix: string }[]; must_fix_count: number } | null;
    attempts: number;
    reason: string | null;
  };
  original: Resume;
};

export type LinkedIn = {
  headline: string[];
  about: string[];
  experience_rewrites: { exp_id: string; scope: string; bullets: string[] }[];
  skills_order: { name: string; pinned: boolean }[];
  keyword_gaps: { term: string; status: "addable-now" | "needs-work"; note: string }[];
  consistency_check: { field: string; resume_value: string | null; linkedin_value: string | null; correct_value: string }[];
  profile_strength: { score: number; components: Component[]; top_changes: string[] };
  featured_suggestions: { item: string; why: string }[];
};

export type Plan = {
  pattern_gaps: { skill: string; blocks_n_jobs: number; pct_of_targets: number; acquisition_difficulty: string }[];
  score_ceiling: { change: string; jobs_moved: string[]; expected_band_shift: string };
  positioning: { verdict: string; commit_to: string[]; drop: string[] };
  evidence_debt: { skill: string; risk: string }[];
  plan: {
    rank: number;
    action: string;
    why_this_one: string;
    effort_hours: number;
    cost: string;
    timeline: string;
    proof_artifact: string;
    jobs_unlocked: string[];
  }[];
  one_line_verdict: string;
};

export type Proposal = {
  certification: Certification;
  skills_covered: string[];
  verified: boolean;
  duplicate_of: string | null;
  needs_review: string[];
  downstream: { roles_strengthened: string[]; gaps_closed: string[]; stale_resumes: string[] };
  confirmation_prompt: string;
  linkedin_add_url: string;
};
export type CredentialsResponse = {
  certifications: Certification[];
  history: { version: number; change: string; at: string }[];
  pending: { proposal_id: string; proposal: Proposal }[];
};

export type RunEvent = { agent: string; status: "started" | "succeeded" | "failed"; detail: string };
