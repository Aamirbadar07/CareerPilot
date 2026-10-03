import assert from "node:assert/strict";
import { test } from "node:test";
import { diffWords } from "./diff.ts";

const shape = (before: string, after: string) => diffWords(before, after).map((p) => [p.kind, p.text]);

test("unchanged text is one same part", () => {
  assert.deepEqual(shape("built a chatbot", "built a chatbot"), [["same", "built a chatbot"]]);
});

test("a replaced word shows as a removal and an addition", () => {
  assert.deepEqual(shape("Built a RAG chatbot over documents", "Built a RAG pipeline over documents"), [
    ["same", "Built a RAG"],
    ["add", "pipeline"],
    ["remove", "chatbot"],
    ["same", "over documents"],
  ]);
});

test("a cut line is all removal and a new line is all addition", () => {
  assert.deepEqual(shape("worked on a script", ""), [["remove", "worked on a script"]]);
  assert.deepEqual(shape("", "deployed with CI/CD"), [["add", "deployed with CI/CD"]]);
});

test("both sides can be rebuilt from the parts", () => {
  const before = "Responsible for writing prompt templates for the support assistant.";
  const after = "Wrote the prompt templates used by the support assistant.";
  const parts = diffWords(before, after);
  const side = (kind: string) => parts.filter((p) => p.kind === "same" || p.kind === kind).map((p) => p.text).join(" ");
  assert.equal(side("remove"), before);
  assert.equal(side("add"), after);
});
