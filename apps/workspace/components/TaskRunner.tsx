"use client";

import { useEffect, useRef, useState } from "react";

interface JobEvent {
  id: number;
  event_type: string;
  payload: Record<string, unknown>;
  created_at: string;
}

const TERMINAL_TYPES = new Set(["SUCCEEDED", "FAILED", "CANCELLED"]);

// Phase 3 (V0.2 human workspace): proves the job/worker/SSE plumbing end to
// end against the stub pipeline in app.worker. Deliberately plain --
// Phase 6 replaces this with the real project view + result screen once
// Phase 4/5 give it real work and real cost/reuse numbers to show.
export default function TaskRunner() {
  const [taskText, setTaskText] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [events, setEvents] = useState<JobEvent[]>([]);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    return () => eventSourceRef.current?.close();
  }, []);

  async function startTask() {
    if (!taskText.trim()) return;
    setError(null);
    setEvents([]);
    setDone(false);

    const response = await fetch("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task_text: taskText }),
    });
    if (!response.ok) {
      setError("Could not start the task.");
      return;
    }
    const job = await response.json();
    setJobId(job.id);

    const source = new EventSource(`/api/jobs/${job.id}/events`);
    eventSourceRef.current = source;
    source.onmessage = (message) => {
      const event: JobEvent = JSON.parse(message.data);
      setEvents((prev) => [...prev, event]);
      if (TERMINAL_TYPES.has(event.event_type)) {
        setDone(true);
        source.close();
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
    <div className="mt-8 rounded-card border border-border bg-surface p-6">
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
            onClick={startTask}
            className="rounded-pill bg-accent px-5 py-2.5 text-[14px] font-semibold text-white"
          >
            Start research
          </button>
        )}
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
  );
}
