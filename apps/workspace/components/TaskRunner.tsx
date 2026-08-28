"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import ResultScreen from "./ResultScreen";

interface JobEvent {
  id: number;
  event_type: string;
  payload: Record<string, unknown>;
  created_at: string;
}

interface JobDetail {
  status: string;
  run_id: string | null;
  project_id: string;
  error_message: string | null;
}

const TERMINAL_TYPES = new Set(["SUCCEEDED", "FAILED", "CANCELLED"]);

// Phase 7: a real 3-way provider choice. "Auto - Best value" (the spec's
// own default) is Phase 9 -- routing individual steps to different models
// automatically isn't built yet, so it isn't offered as a choice here.
const MODEL_OPTIONS: { value: string; label: string }[] = [
  { value: "openai", label: "GPT-4o mini" },
  { value: "anthropic", label: "Claude Haiku 4.5" },
  { value: "gemini", label: "Gemini 3.6 Flash" },
];

// Phases 3-7 (V0.2 human workspace): task input -> live SSE progress ->
// (Phase 6) the real result screen once the job succeeds, backed by the
// run's actual recorded cost/reuse numbers rather than a placeholder.
export default function TaskRunner() {
  const [taskText, setTaskText] = useState("");
  const [modelPreference, setModelPreference] = useState(MODEL_OPTIONS[0].value);
  const [jobId, setJobId] = useState<string | null>(null);
  const [events, setEvents] = useState<JobEvent[]>([]);
  const [done, setDone] = useState(false);
  const [job, setJob] = useState<JobDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    return () => eventSourceRef.current?.close();
  }, []);

  async function startTask(modelOverride?: string) {
    if (!taskText.trim()) return;
    const model = modelOverride ?? modelPreference;
    setModelPreference(model);
    setError(null);
    setEvents([]);
    setDone(false);
    setJob(null);

    const response = await fetch("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task_text: taskText, model_preference: model }),
    });
    if (!response.ok) {
      setError("Could not start the task.");
      return;
    }
    const created = await response.json();
    setJobId(created.id);

    const source = new EventSource(`/api/jobs/${created.id}/events`);
    eventSourceRef.current = source;
    source.onmessage = async (message) => {
      const event: JobEvent = JSON.parse(message.data);
      setEvents((prev) => [...prev, event]);
      if (TERMINAL_TYPES.has(event.event_type)) {
        setDone(true);
        source.close();
        const jobResponse = await fetch(`/api/jobs/${created.id}`);
        if (jobResponse.ok) setJob(await jobResponse.json());
      }
    };
    source.onerror = () => {
      source.close();
    };
  }

  async function cancelTask() {
    if (!jobId) return;
    await fetch(`/api/jobs/${jobId}/cancel`, { method: "POST" });
  }

  const running = jobId !== null && !done;

  return (
    <div>
      <div className="rounded-card border border-border bg-surface p-6">
        <div className="flex gap-2">
          <input
            type="text"
            value={taskText}
            onChange={(e) => setTaskText(e.target.value)}
            disabled={running}
            placeholder="Research today's AI infrastructure news..."
            className="flex-1 rounded-2xl border border-border bg-page px-4 py-2.5 text-[14px] text-ink outline-none focus:border-accent disabled:opacity-60"
          />
          {running ? (
            <button
              type="button"
              onClick={cancelTask}
              className="rounded-pill border border-border px-5 py-2.5 text-[14px] font-semibold text-ink-secondary hover:text-ink"
            >
              Cancel
            </button>
          ) : (
            <button
              type="button"
              onClick={() => startTask()}
              className="rounded-pill bg-accent px-5 py-2.5 text-[14px] font-semibold text-white"
            >
              Start research
            </button>
          )}
        </div>

        <div className="mt-2 flex items-center gap-2 text-[13px] text-ink-muted">
          Model
          <select
            value={modelPreference}
            onChange={(e) => setModelPreference(e.target.value)}
            disabled={running}
            className="rounded-pill border border-border bg-page px-3 py-1 text-[13px] text-ink outline-none focus:border-accent disabled:opacity-60"
          >
            {MODEL_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        {error ? <p className="mt-3 text-[13.5px] text-critical">{error}</p> : null}

        {events.length > 0 ? (
          <ul className="mt-5 flex flex-col gap-2">
            {events.map((event) => (
              <li
                key={event.id}
                className="flex items-center gap-2 text-[13.5px] text-ink-secondary"
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
          </ul>
        ) : null}
      </div>

      {job?.status === "SUCCEEDED" && job.run_id ? (
        <>
          <ResultScreen
            runId={job.run_id}
            currentModel={modelPreference}
            onSwitchModel={(model) => startTask(model)}
          />
          <Link
            href={`/projects/${job.project_id}`}
            className="mt-3 block text-center text-[13px] text-ink-muted hover:text-ink"
          >
            View project &rarr;
          </Link>
        </>
      ) : null}

      {job?.status === "FAILED" ? (
        <div className="mt-8 rounded-card border border-border bg-surface p-6 text-center">
          <p className="text-[14px] text-critical">
            {job.error_message === "cost cap reached"
              ? "This task hit its cost limit and stopped."
              : "Something went wrong."}
          </p>
        </div>
      ) : null}
    </div>
  );
}
