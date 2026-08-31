"use client";

import type { JobDetail, JobEvent } from "@/lib/api";
import { extractFileBlocks } from "@/lib/fileBlocks";
import FileCard from "./FileCard";
import MarkdownAnswer from "./MarkdownAnswer";
import ResultScreen from "./ResultScreen";

const TERMINAL_TYPES = new Set(["SUCCEEDED", "FAILED", "CANCELLED"]);

// The real, fixed pipeline (app/agent/pipeline.py's run_research_pipeline)
// -- these are the only `payload.step` values STEP_STARTED/STEP_FINISHED
// ever carry, and always fire in this order. Friendly labels in place of
// the raw step name.
const STEP_LABELS: Record<string, string> = {
  search_sources: "Searching sources",
  extract_facts: "Extracting facts",
  research_background: "Researching background",
  analyze: "Analyzing",
  write_draft: "Writing draft",
  fact_check: "Fact-checking",
};
const STEP_ORDER = Object.keys(STEP_LABELS);

type ProgressRow = { key: string; label: string; done: boolean };

// Turns the flat event log into one row per step (collapsing that step's
// own STARTED+FINISHED pair into a single line that flips from "in
// progress" to "done", instead of appending a second raw line once it
// finishes) -- a step only appears once its own STEP_STARTED has actually
// arrived, so this reads as a live reveal of real work, not a static
// checklist. Before the first step starts, falls back to a single
// "Waiting in queue"/"Starting" row so the list is never empty while
// something real is happening server-side (job picked up, run
// provisioning) that just doesn't have its own step yet.
function buildProgressRows(events: JobEvent[]): ProgressRow[] {
  const stepDone = new Map<string, boolean>();
  let started = false;
  for (const event of events) {
    if (event.event_type === "STARTED") started = true;
    const step = event.payload.step;
    if (typeof step !== "string") continue;
    if (event.event_type === "STEP_STARTED" && !stepDone.has(step)) stepDone.set(step, false);
    if (event.event_type === "STEP_FINISHED") stepDone.set(step, true);
  }
  const rows = STEP_ORDER.filter((step) => stepDone.has(step)).map((step) => ({
    key: step,
    label: STEP_LABELS[step],
    done: stepDone.get(step) === true,
  }));
  if (rows.length === 0) {
    rows.push({ key: "status", label: started ? "Starting" : "Waiting in queue", done: false });
  }
  return rows;
}

// Phase 10: app.worker classifies a real provider/network failure
// separately from any other bug (error_message "provider unavailable" vs
// "internal error") -- worth a distinct, more honest message here rather
// than folding every failure into one generic line.
function failureMessage(errorMessage: string | null): string {
  if (errorMessage === "cost cap reached") return "This task hit its cost limit and stopped.";
  if (errorMessage === "provider unavailable") {
    return "One of the AI providers is temporarily unavailable. Please try again shortly.";
  }
  return "Something went wrong. Please try again.";
}

// One turn from the V0.3 Figma design ("Registered user" flow): the user's
// message as a filled warm bubble, the assistant's answer as plain text
// (no bubble -- matches the design, which only fills the user's turn),
// then -- once the turn succeeds -- the receipt/compute-details block
// (ResultScreen, restyled in this same pass to match the Figma "N sources
// reused" line) and a live progress list while it's still running.
export default function TurnBubble({
  job,
  events,
  isActive,
  partialText,
  modelPreference,
  onSwitchModel,
  onRegenerate,
}: {
  job: JobDetail;
  events: JobEvent[];
  isActive: boolean;
  //: The in-flight assistant reply for chat turns, streamed in via `delta`
  //: envelopes on GET /jobs/{id}/stream (see ChatThread.tsx) -- empty for
  //: every turn except the one currently streaming.
  partialText: string;
  modelPreference: string;
  onSwitchModel: (model: string) => void;
  onRegenerate: () => void;
}) {
  const running = isActive && !TERMINAL_TYPES.has(job.status) && job.status !== "QUEUED";
  const queued = isActive && job.status === "QUEUED";
  const fileBlocks = job.answer_text ? extractFileBlocks(job.answer_text) : [];

  return (
    <div className="flex flex-col gap-4">
      <div className="max-w-[900px] whitespace-pre-wrap rounded-[20px] rounded-br-none bg-chat-warm p-4 text-[16px] text-chat-ink-soft">
        {job.task_text}
      </div>

      {isActive && partialText ? (
        // Chat streaming: once the first `delta` chunk has arrived, show
        // the accumulating answer itself instead of the step checklist
        // below -- that checklist still renders (empty events, so it falls
        // straight to "Waiting in queue"/"Starting") as the brief loading
        // indicator for the moment before the first token arrives.
        <MarkdownAnswer text={partialText} />
      ) : queued || running ? (
        <ul className="flex flex-col gap-1.5">
          {buildProgressRows(events).map((row) =>
            row.done ? (
              <li key={row.key} className="flex items-center gap-2 text-[13.5px] text-chat-ink-soft">
                <span className="h-1.5 w-1.5 rounded-full bg-good" />
                {row.label}
              </li>
            ) : (
              // The same looping video as every other "Accurate is doing
              // something" spot (auth loading, empty-state hero) instead of
              // a plain dot -- standard leading icon for whichever state is
              // currently active, so it stays visually constant across
              // Waiting in queue / Starting / each step's own text rather
              // than being tied to one specific state's copy.
              <li key={row.key} className="flex items-center gap-[6px] text-[13.5px] text-chat-ink-soft">
                {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
                <video
                  src="/videos/social-loading.mp4"
                  autoPlay
                  loop
                  muted
                  playsInline
                  className="h-[35px] w-[35px] shrink-0 rounded-full object-cover"
                />
                {row.label}…
              </li>
            )
          )}
        </ul>
      ) : null}

      {job.status === "SUCCEEDED" && job.answer_text ? (
        <>
          <MarkdownAnswer text={job.answer_text} />
          {fileBlocks.length > 0 ? (
            <div className="flex flex-wrap gap-3">
              {fileBlocks.map((block) => (
                <FileCard key={block.id} block={block} />
              ))}
            </div>
          ) : null}
        </>
      ) : null}

      {job.status === "SUCCEEDED" && job.run_id ? (
        <ResultScreen
          runId={job.run_id}
          currentModel={modelPreference}
          onSwitchModel={onSwitchModel}
        />
      ) : null}

      {job.status === "FAILED" || job.status === "SUCCEEDED" ? (
        // Regenerate now also offers a re-roll on a SUCCEEDED turn, not
        // just a way to recover from FAILED -- the failure message stays
        // scoped to the FAILED case on its own, since it's not applicable
        // (and job.error_message is null) once a turn has succeeded.
        <div className="flex items-center gap-3">
          {job.status === "FAILED" ? (
            <p className="text-[14px] text-critical">{failureMessage(job.error_message)}</p>
          ) : null}
          <button
            type="button"
            onClick={onRegenerate}
            className="shrink-0 rounded-pill border border-chat-border-warm px-3.5 py-1 text-[13px] font-semibold text-chat-ink hover:bg-chat-warm"
          >
            Regenerate
          </button>
        </div>
      ) : null}

      {job.status === "CANCELLED" ? (
        <p className="text-[14px] text-chat-ink-soft">This task was cancelled.</p>
      ) : null}
    </div>
  );
}
