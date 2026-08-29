"use client";

import { useEffect, useRef, useState } from "react";
import type { JobDetail, JobEvent } from "@/lib/api";
import AiOrb from "./AiOrb";
import Composer, { MODEL_OPTIONS } from "./Composer";
import TurnBubble from "./TurnBubble";

const TERMINAL_TYPES = new Set(["SUCCEEDED", "FAILED", "CANCELLED"]);

const SUGGESTIONS: { label: string; icon: string; prompt: string }[] = [
  {
    label: "Create",
    icon: "/icons/suggestion-create.svg",
    prompt: "Create a one-page brief on ",
  },
  {
    label: "Code",
    icon: "/icons/suggestion-code.svg",
    prompt: "Help me plan how to build ",
  },
  { label: "Write", icon: "/icons/suggestion-write.svg", prompt: "Write a draft about " },
  {
    label: "Learn",
    icon: "/icons/suggestion-learn.svg",
    prompt: "Explain, with current sources, ",
  },
  {
    label: "Just Life",
    icon: "/icons/suggestion-create.svg",
    prompt: "Research today's news on ",
  },
];

// The chat thread from the V0.3 Figma design ("Registered user" flow): an
// empty state (orb + greeting + heading + composer + suggestions) that
// becomes a turn-by-turn conversation once the first message is sent.
// Each turn is a Job (see lib/api.ts's JobDetail) -- no separate message
// model, matching the V0.3 plan's "Job-as-turn" simplification.
export default function ChatThread({
  initialProjectId,
  initialTurns,
}: {
  initialProjectId: string | null;
  initialTurns: JobDetail[];
}) {
  const [projectId, setProjectId] = useState(initialProjectId);
  const [turns, setTurns] = useState<JobDetail[]>(initialTurns);
  const [taskText, setTaskText] = useState("");
  const [modelPreference, setModelPreference] = useState(MODEL_OPTIONS[0].value);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [activeEvents, setActiveEvents] = useState<JobEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    return () => eventSourceRef.current?.close();
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, activeEvents]);

  async function submit(text: string, model: string) {
    if (!text.trim() || activeJobId) return;
    setError(null);
    setModelPreference(model);

    const response = await fetch("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task_text: text, model_preference: model }),
    });
    if (!response.ok) {
      setError("Could not start the task.");
      return;
    }
    const created: JobDetail = await response.json();
    if (!projectId) setProjectId(created.project_id);
    setTurns((prev) => [...prev, created]);
    setActiveJobId(created.id);
    setActiveEvents([]);
    setTaskText("");

    const source = new EventSource(`/api/jobs/${created.id}/events`);
    eventSourceRef.current = source;
    source.onmessage = async (message) => {
      const event: JobEvent = JSON.parse(message.data);
      setActiveEvents((prev) => [...prev, event]);
      if (TERMINAL_TYPES.has(event.event_type)) {
        source.close();
        const jobResponse = await fetch(`/api/jobs/${created.id}`);
        if (jobResponse.ok) {
          const finished: JobDetail = await jobResponse.json();
          setTurns((prev) => prev.map((t) => (t.id === finished.id ? finished : t)));
        }
        setActiveJobId(null);
      }
    };
    source.onerror = () => source.close();
  }

  async function cancelActive() {
    if (!activeJobId) return;
    await fetch(`/api/jobs/${activeJobId}/cancel`, { method: "POST" });
  }

  const running = activeJobId !== null;
  const hasTurns = turns.length > 0;

  return (
    <div className="relative flex min-h-screen flex-1 flex-col overflow-hidden">
      {!hasTurns ? (
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 bottom-0 h-[70vh] opacity-70"
          style={{
            background:
              "radial-gradient(60% 60% at 50% 100%, var(--chat-accent-strong) 0%, var(--accent-soft) 45%, transparent 75%)",
            filter: "blur(60px)",
          }}
        />
      ) : null}
      <div className="relative mx-auto flex w-full max-w-[900px] flex-1 flex-col px-6 py-10">
        {!hasTurns ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-6 text-center">
            <div className="rounded-[20px] bg-chat-warm px-6 py-5">
              <p className="max-w-[342px] text-[16px] text-chat-ink-soft">
                Hi there and nice to meet you, I&apos;m Accurate, and I&apos;m here to help you!
              </p>
            </div>
            <AiOrb size={112.5} />
            <h1 className="font-display max-w-[652px] text-[26px] font-medium text-chat-ink">
              Create, build, research or work with{" "}
              <span className="text-chat-accent-strong">less tokens</span>
            </h1>

            <div className="w-full max-w-[676px]">
              <Composer
                value={taskText}
                onChange={setTaskText}
                onSubmit={() => submit(taskText, modelPreference)}
                onCancel={cancelActive}
                running={running}
                placeholder="Ask me anything you want to do today!"
                modelPreference={modelPreference}
                onModelChange={setModelPreference}
              />
            </div>

            <div className="flex items-center gap-2.5 text-[14px] text-chat-ink">
              <span>Start with</span>
              <div className="flex flex-wrap items-center justify-center gap-1">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s.label}
                    type="button"
                    onClick={() => setTaskText(s.prompt)}
                    className="flex items-center gap-1 rounded-pill bg-chat-warm px-2.5 py-1.5 text-[14px] text-chat-label"
                  >
                    <img src={s.icon} alt="" className="h-3.5 w-3.5" />
                    {s.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <>
            <div className="flex flex-1 flex-col gap-10 pb-6">
              {turns.map((turn) => (
                <TurnBubble
                  key={turn.id}
                  job={turn}
                  events={turn.id === activeJobId ? activeEvents : []}
                  isActive={turn.id === activeJobId}
                  modelPreference={modelPreference}
                  onSwitchModel={(model) => submit(turn.task_text, model)}
                />
              ))}
              <div ref={bottomRef} />
            </div>

            <div className="sticky bottom-6">
              <Composer
                value={taskText}
                onChange={setTaskText}
                onSubmit={() => submit(taskText, modelPreference)}
                onCancel={cancelActive}
                running={running}
                placeholder="Write message"
                modelPreference={modelPreference}
                onModelChange={setModelPreference}
              />
            </div>
          </>
        )}

        {error ? <p className="mt-3 text-[13.5px] text-critical">{error}</p> : null}
      </div>
    </div>
  );
}
