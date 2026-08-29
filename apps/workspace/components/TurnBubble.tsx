"use client";

import type { JobDetail, JobEvent } from "@/lib/api";
import ResultScreen from "./ResultScreen";

const TERMINAL_TYPES = new Set(["SUCCEEDED", "FAILED", "CANCELLED"]);

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
  modelPreference,
  onSwitchModel,
}: {
  job: JobDetail;
  events: JobEvent[];
  isActive: boolean;
  modelPreference: string;
  onSwitchModel: (model: string) => void;
}) {
  const running = isActive && !TERMINAL_TYPES.has(job.status) && job.status !== "QUEUED";
  const queued = isActive && job.status === "QUEUED";

  return (
    <div className="flex flex-col gap-4">
      <div className="max-w-[900px] whitespace-pre-wrap rounded-[20px] rounded-br-none bg-chat-warm p-4 text-[16px] text-chat-ink-soft">
        {job.task_text}
      </div>

      {queued || running ? (
        <ul className="flex flex-col gap-1.5">
          {events.map((event) => (
            <li
              key={event.id}
              className="flex items-center gap-2 text-[13.5px] text-chat-ink-soft"
            >
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  TERMINAL_TYPES.has(event.event_type) ? "bg-good" : "bg-accent"
                }`}
              />
              {event.event_type}
              {typeof event.payload.step === "string" ? `: ${event.payload.step}` : ""}
            </li>
          ))}
          {events.length === 0 ? (
            <li className="text-[13.5px] text-chat-ink-soft">Starting&hellip;</li>
          ) : null}
        </ul>
      ) : null}

      {job.status === "SUCCEEDED" && job.answer_text ? (
        <div className="max-w-[900px] whitespace-pre-wrap text-[16px] font-medium text-chat-ink">
          {job.answer_text}
        </div>
      ) : null}

      {job.status === "SUCCEEDED" && job.run_id ? (
        <ResultScreen
          runId={job.run_id}
          currentModel={modelPreference}
          onSwitchModel={onSwitchModel}
        />
      ) : null}

      {job.status === "FAILED" ? (
        <p className="text-[14px] text-critical">{failureMessage(job.error_message)}</p>
      ) : null}

      {job.status === "CANCELLED" ? (
        <p className="text-[14px] text-chat-ink-soft">This task was cancelled.</p>
      ) : null}
    </div>
  );
}
