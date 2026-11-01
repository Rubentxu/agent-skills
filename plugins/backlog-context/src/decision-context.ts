/**
 * Pure, bounded join over native Backlog.md CLI JSON.
 * Source text, titles and agent opinions are deliberately excluded.
 * "accepted" remains only a documentary state, NOT verified human authority.
 */
import { asRecord, validTaskId } from "./kernel.ts";

const DECISION = /^decision-[1-9][0-9]{0,8}$/;
type Rows = Record<string, unknown>[];
export type CandidateLinks = { tasks: string[]; ids: string[] };
export type DecisionLinks = { tasks: string[]; decisions: { id: string; status: string }[]; missing: number };
const validEnvelope = (input: unknown, kind: string, field: string): Rows | null => {
  const root = asRecord(input);
  if (!root || root.schemaVersion !== 1 || root.kind !== kind ||
      !Array.isArray(root[field]) || root[field].length > 10000 ||
      root[field].some((v: unknown) => !asRecord(v)) ||
      (root.nextSkip !== undefined && root.nextSkip !== null) ||
      (root.total !== undefined && root.total !== (root[field] as unknown[]).length)) return null;
  return root[field] as Rows;
};

const decisionRef = (value: unknown): string | null => {
  if (typeof value !== "string" || value.length > 256) return null;
  if (DECISION.test(value)) return value;
  const match = /^backlog\/decisions\/(decision-[1-9][0-9]{0,8})\.md$/.exec(value);
  return match ? match[1] : null;
};
const strings = (input: unknown): string[] =>
  Array.isArray(input) && input.length <= 256 && input.every(x => typeof x === "string")
    ? input : [];

export function candidateDecisionLinks(
  taskList: unknown, file: string, owner?: string, activeTaskId?: string,
): CandidateLinks | null {
  const tasks = validEnvelope(taskList, "task-list", "tasks");
  if (!tasks || typeof file !== "string" || file.length > 4096 ||
      (activeTaskId !== undefined && !validTaskId(activeTaskId))) return null;
  // Selecting an explicitly provided task prevents accidental cross-task memory.
  const matches = tasks.map(task => {
    const id = task.id;
    if (!validTaskId(id) || task.archived === true) return null;
    const refs = strings(task.references);
    const paths = strings(task.modifiedFiles);
    const score = activeTaskId
      ? (id === activeTaskId ? 100 : 0)
      : (owner && refs.includes(owner) ? 10 : 0) + (paths.includes(file) ? 1 : 0);
    return score > 0 ? { id, score, refs } : null;
  }).filter((x): x is { id: string; score: number; refs: string[] } => x !== null)
    .sort((a, b) => b.score - a.score || a.id.localeCompare(b.id));
  if (!matches.length || matches.length > 3) return null; // Ambiguous association -> no guess.
  const ids = [...new Set(matches.flatMap(x => x.refs.map(decisionRef)
    .filter((x): x is string => x !== null)))].slice(0, 5);
  return ids.length ? { tasks: matches.map(x => x.id), ids } : null;
}

export function resolveDecisionLinks(
  candidates: CandidateLinks, decisionList: unknown,
): DecisionLinks | null {
  const rows = validEnvelope(decisionList, "decision-list", "decisions");
  if (!rows || !Array.isArray(candidates.ids) || candidates.ids.length > 5) return null;
  const byId = new Map<string, string>();
  for (const row of rows) {
    if (typeof row.id !== "string" || !DECISION.test(row.id) || byId.has(row.id)) return null;
    const status = typeof row.status === "string" &&
      /^(?:proposed|accepted|approved|superseded|rejected|draft)$/.test(row.status)
      ? row.status : "unknown";
    byId.set(row.id, status);
  }
  const decisions = candidates.ids.filter(id => byId.has(id))
    .map(id => ({ id, status: byId.get(id)! }));
  return { tasks: candidates.tasks, decisions,
    missing: candidates.ids.length - decisions.length };
}

export function presentDecisionLinks(value: DecisionLinks): string | null {
  if (!value.decisions.length && !value.missing) return null;
  const taskIds = value.tasks.filter(validTaskId).slice(0, 3);
  const entries = value.decisions.slice(0, 5).map(x => x.id + " [" + x.status + "]").join(", ");
  return "Backlog (vínculos explícitos, SOLO contexto): tareas " + taskIds.join(", ") +
    "; decisiones " + (entries || "sin resolución") +
    (value.missing ? "; " + value.missing + " referencia(s) no encontrada(s)" : "") +
    ". El estado entre corchetes es DOCUMENTAL, no acredita autoría ni autorización. " +
    "Consulta el original humano y la lente decision-provenance antes de aplicar una política. " +
    "La lista se obtuvo por referencias exactas, sin comparar títulos ni interpretar conversaciones.";
}
