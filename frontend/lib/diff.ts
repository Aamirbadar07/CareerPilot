export type Part = { text: string; kind: "same" | "add" | "remove" };

/** Word-level diff by longest common subsequence. Resume bullets are short, so the
 *  quadratic table is tiny. */
export function diffWords(before: string, after: string): Part[] {
  const a = before.split(/\s+/).filter(Boolean);
  const b = after.split(/\s+/).filter(Boolean);
  const lcs = Array.from({ length: a.length + 1 }, () => new Array<number>(b.length + 1).fill(0));
  for (let i = a.length - 1; i >= 0; i--)
    for (let j = b.length - 1; j >= 0; j--)
      lcs[i][j] = a[i] === b[j] ? lcs[i + 1][j + 1] + 1 : Math.max(lcs[i + 1][j], lcs[i][j + 1]);

  const parts: Part[] = [];
  const push = (text: string, kind: Part["kind"]) => {
    const last = parts[parts.length - 1];
    if (last?.kind === kind) last.text += " " + text;
    else parts.push({ text, kind });
  };
  let i = 0;
  let j = 0;
  while (i < a.length || j < b.length) {
    if (i < a.length && j < b.length && a[i] === b[j]) {
      push(a[i++], "same");
      j++;
    } else if (j < b.length && (i === a.length || lcs[i][j + 1] >= lcs[i + 1][j])) push(b[j++], "add");
    else push(a[i++], "remove");
  }
  return parts;
}
