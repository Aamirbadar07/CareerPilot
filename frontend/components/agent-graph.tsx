// The seven agents and the one object they share. Edges are real data flow: everything
// reads the master profile, and a new credential writes back to it. Pulses are SMIL motion
// along each edge, hidden for prefers-reduced-motion.

type Node = { id: string; label: string; x: number; y: number };

const W = 132;
const H = 40;

const NODES: Node[] = [
  { id: "analyzer", label: "Resume analyzer", x: 12, y: 96 },
  { id: "credentials", label: "Credentials", x: 12, y: 284 },
  { id: "discovery", label: "Job discovery", x: 416, y: 12 },
  { id: "fit", label: "Fit scorer", x: 416, y: 100 },
  { id: "tailor", label: "Resume tailor", x: 416, y: 188 },
  { id: "linkedin", label: "LinkedIn optimizer", x: 416, y: 276 },
  { id: "coach", label: "Career coach", x: 416, y: 364 },
];

const HUB = { x: 280, y: 208, r: 54 };

// [path, pulse duration in seconds, delay]
const EDGES: [string, number, number][] = [
  ["M144 116 C 200 116, 200 190, 228 198", 2.6, 0],
  ["M144 304 C 200 304, 200 230, 228 220", 3.4, 1.2],
  ["M326 180 C 370 150, 370 32, 416 32", 2.8, 0.4],
  ["M482 52 L 482 100", 1.6, 1.0],
  ["M482 140 L 482 188", 1.6, 1.8],
  ["M334 204 C 370 204, 380 208, 416 208", 2.4, 0.9],
  ["M330 228 C 370 250, 370 296, 416 296", 2.8, 1.5],
  ["M548 120 C 572 200, 572 330, 548 380", 3.2, 2.2],
];

export function AgentGraph() {
  return (
    <svg
      viewBox="0 0 580 416"
      role="img"
      aria-label="Seven agents connected through one master profile: the resume analyzer and credentials agent write to it; job discovery, fit scorer, resume tailor, LinkedIn optimizer and career coach read from it."
      className="h-auto w-full"
    >
      <defs>
        <linearGradient id="accent" x1="0" x2="1">
          <stop offset="0" stopColor="var(--accent-from)" />
          <stop offset="1" stopColor="var(--accent-to)" />
        </linearGradient>
      </defs>

      {EDGES.map(([d, dur, begin], i) => (
        <g key={i}>
          <path d={d} fill="none" stroke="var(--border-strong)" strokeWidth="1.25" />
          <circle r="3.5" fill="url(#accent)" className="motion-reduce:hidden">
            <animateMotion dur={`${dur}s`} begin={`${begin}s`} repeatCount="indefinite" path={d} />
          </circle>
        </g>
      ))}

      <circle cx={HUB.x} cy={HUB.y} r={HUB.r} fill="var(--surface)" stroke="url(#accent)" strokeWidth="1.5" />
      <text x={HUB.x} y={HUB.y - 4} textAnchor="middle" fill="var(--fg)" fontSize="13" fontWeight="600">
        Master
      </text>
      <text x={HUB.x} y={HUB.y + 14} textAnchor="middle" fill="var(--fg)" fontSize="13" fontWeight="600">
        profile
      </text>

      {NODES.map((n) => (
        <g key={n.id}>
          <rect x={n.x} y={n.y} width={W} height={H} rx="10" fill="var(--surface)" stroke="var(--border-strong)" />
          <text x={n.x + W / 2} y={n.y + 25} textAnchor="middle" fill="var(--fg)" fontSize="12.5">
            {n.label}
          </text>
        </g>
      ))}
    </svg>
  );
}
