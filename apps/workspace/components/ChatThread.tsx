"use client";

import { useEffect, useRef, useState } from "react";
import type { ChatStreamEnvelope, JobDetail, JobEvent } from "@/lib/api";
import Composer, { MODEL_OPTIONS } from "./Composer";
import GradientBackground from "./GradientBackground";
import TurnBubble from "./TurnBubble";

const TERMINAL_TYPES = new Set(["SUCCEEDED", "FAILED", "CANCELLED"]);

// The empty state's greeting bubble rotates through these every 5s (Figma
// node 96-2349, "Accurate buble talk slider options" -- annotated "slides
// at 5 seconds max with a smooth transition").
const GREETING_MESSAGES = [
  "Hi there and nice to meet you, I'm Accurate, and I'm here to help you!",
  "I'm integrated best with OpenRouter",
  "And you can use through my interface +100 LLMs models",
];
const GREETING_INTERVAL_MS = 5000;
const GREETING_TRANSITION_MS = 300;

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
  initialTitle,
}: {
  initialProjectId: string | null;
  initialTurns: JobDetail[];
  //: V0.3 conversation history: the conversation's current title, shown
  //: at the top of the content area. Null only for a brand-new, not-yet-
  //: started conversation (no title to show until the first message).
  initialTitle: string | null;
}) {
  const [projectId, setProjectId] = useState(initialProjectId);
  const [turns, setTurns] = useState<JobDetail[]>(initialTurns);
  const [title, setTitle] = useState(initialTitle);
  const [taskText, setTaskText] = useState("");
  const [modelPreference, setModelPreference] = useState(MODEL_OPTIONS[0].value);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [activeEvents, setActiveEvents] = useState<JobEvent[]>([]);
  //: The in-flight assistant reply, accumulated from `delta` chunks on the
  //: chat stream (see submit() below) -- reset alongside activeEvents.
  const [activePartialText, setActivePartialText] = useState("");
  //: The cancel POST resolves almost immediately, but the job itself only
  //: actually stops up to CANCELLATION_POLL_SECONDS (0.5s) later, on its
  //: next checkpoint -- without this, a click during that gap looked
  //: completely inert and invited a second (or third) click.
  const [cancelling, setCancelling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const contentColumnRef = useRef<HTMLDivElement | null>(null);
  // Measured (not hardcoded) horizontal box for the gradient background,
  // so it centers on the actual content column -- wherever that column
  // really sits after the sidebar -- instead of a guessed sidebar-width
  // offset that drifts if the sidebar's width or the viewport changes.
  const [gradientBox, setGradientBox] = useState<{ left: number; width: number } | null>(null);

  useEffect(() => {
    const el = contentColumnRef.current;
    if (!el) return;
    const GRADIENT_EXTRA_WIDTH_PX = 200;
    const measure = () => {
      const rect = el.getBoundingClientRect();
      const width = rect.width + GRADIENT_EXTRA_WIDTH_PX;
      setGradientBox({ left: rect.left + rect.width / 2 - width / 2, width });
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    window.addEventListener("resize", measure);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", measure);
    };
  }, []);

  const hasTurns = turns.length > 0;
  // Drives the empty-state -> populated-thread transition: the empty
  // composer only ever appears once, before the first message, so this
  // needs to read as a smooth handoff rather than a hard swap. React
  // unmounts a conditional branch immediately with no chance for an exit
  // animation, so the empty view is kept mounted (fading out) for one
  // transition before actually switching to the thread view -- see
  // app/globals.css's .chat-thread-in for the entrance side.
  const [showEmpty, setShowEmpty] = useState(!hasTurns);
  const [fadingOut, setFadingOut] = useState(false);
  const [greetingIndex, setGreetingIndex] = useState(0);
  // "out" plays the current message sliding away; only once that's had
  // time to finish does the index advance and "in" slide the next one in
  // -- see app/globals.css's .greeting-slide-out/-in -- so the two never
  // overlap on screen.
  const [greetingPhase, setGreetingPhase] = useState<"in" | "out">("in");

  useEffect(() => {
    if (hasTurns && showEmpty && !fadingOut) setFadingOut(true);
  }, [hasTurns, showEmpty, fadingOut]);

  useEffect(() => {
    if (!showEmpty) return;
    let outTimeout: ReturnType<typeof setTimeout> | undefined;
    const intervalId = setInterval(() => {
      setGreetingPhase("out");
      outTimeout = setTimeout(() => {
        setGreetingIndex((i) => (i + 1) % GREETING_MESSAGES.length);
        setGreetingPhase("in");
      }, GREETING_TRANSITION_MS);
    }, GREETING_INTERVAL_MS);
    return () => {
      clearInterval(intervalId);
      if (outTimeout) clearTimeout(outTimeout);
    };
  }, [showEmpty]);

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
      body: JSON.stringify({
        task_text: text,
        model_preference: model,
        // V0.3 conversation history: attach to the current conversation
        // once one exists; omitted (undefined) on the very first message,
        // which is exactly what tells the backend to start a new one.
        project_id: projectId ?? undefined,
      }),
    });
    if (!response.ok) {
      setError("Could not start the task.");
      return;
    }
    const created: JobDetail = await response.json();
    if (!projectId) {
      setProjectId(created.project_id);
      setTitle(created.project_name);
    }
    setTurns((prev) => [...prev, created]);
    setActiveJobId(created.id);
    setActiveEvents([]);
    setActivePartialText("");
    setTaskText("");

    watchJobStream(created.id);
  }

  // Opens the SSE stream for one job (brand-new or reset-for-regenerate --
  // see regenerateActive below) and wires its deltas/completion into the
  // shared active-turn state. Pulled out of submit() so both codepaths
  // (a genuinely new job, and the same job re-run in place) drive the
  // stream identically.
  function watchJobStream(jobId: string) {
    const source = new EventSource(`/api/jobs/${jobId}/stream`);
    eventSourceRef.current = source;
    source.onmessage = (message) => {
      const envelope: ChatStreamEnvelope = JSON.parse(message.data);
      if (envelope.type === "title") {
        // The AI-generated title (V0.3) replaces the fallback set above,
        // usually within a couple seconds -- same as the old
        // PROJECT_TITLED event, just carried over the chat stream now.
        setTitle(envelope.name);
        return;
      }
      if (envelope.type === "delta") {
        setActivePartialText((prev) => prev + envelope.text);
        return;
      }
      // "done": the turn is fully finished (success or failure -- job.status
      // tells which) and envelope.job is already the complete, final
      // JobDetail record, so no extra GET /api/jobs/{id} fetch is needed.
      setTurns((prev) => prev.map((t) => (t.id === envelope.job.id ? envelope.job : t)));
      setActiveJobId(null);
      setActivePartialText("");
      setCancelling(false);
      source.close();
    };
    source.onerror = () => source.close();
  }

  // Regenerate: resets the SAME job (via POST /api/jobs/{id}/regenerate)
  // and re-streams it, rather than calling submit() to create a new job.
  // That distinction is what makes Regenerate a real cl.compute.run() cache
  // hit instead of a fresh (billed) provider call -- see the backend
  // route's own docstring (app/routes/jobs.py's regenerate_job) for why a
  // new job's conversation history differs from the original's.
  async function regenerateActive(jobId: string) {
    if (activeJobId) return;
    setError(null);

    const response = await fetch(`/api/jobs/${jobId}/regenerate`, { method: "POST" });
    if (!response.ok) {
      setError("Could not regenerate this answer.");
      return;
    }
    const reset: JobDetail = await response.json();
    setTurns((prev) => prev.map((t) => (t.id === jobId ? reset : t)));
    setActiveJobId(jobId);
    setActiveEvents([]);
    setActivePartialText("");
    watchJobStream(jobId);
  }

  async function cancelActive() {
    if (!activeJobId || cancelling) return;
    setCancelling(true);
    await fetch(`/api/jobs/${activeJobId}/cancel`, { method: "POST" });
  }

  const running = activeJobId !== null;

  return (
    <div className="relative flex h-full flex-1 flex-col overflow-hidden">
      {title ? (
        // A true static header -- not `sticky`, and not inside the
        // scrolling region below -- so it can never glitch on trackpad
        // overscroll the way a sticky one did. Sits flush against the
        // sidebar (top left, nearby the side navigation, per the
        // original spec) rather than drifting to wherever the centered
        // 900px column lands on a wide viewport.
        <div className="relative z-10 flex shrink-0 items-center gap-1.5 bg-page px-6 pb-3 pt-3">
          <span className="text-[15px] font-medium text-chat-ink">{title}</span>
          <img src="/icons/chevron-down.svg" alt="" className="h-[5.5px] w-[9.5px]" />
          {/* Overlays the top of the scrollable region right below it,
              fading scrolled-past turn text into the page instead of
              hard-clipping it -- mirrors the composer's own fade at
              the bottom. */}
          <div className="pointer-events-none absolute inset-x-0 top-full h-20 bg-gradient-to-b from-page to-transparent" />
        </div>
      ) : null}
      <div className="relative flex flex-1 flex-col overflow-y-auto overscroll-y-contain">
        {/* Mobile only (Figma node 121:3667's populated-scroll frames,
            "Rectangle 427321515"): MobileNav's logo+hamburger header sits
            outside this scrolling region entirely (a shrink-0 flex
            sibling, never inside the scroll container), so it's already
            effectively "sticky" by construction -- this is the fade Figma
            adds right below it, a blurred white gradient that stays
            pinned to the top of the scroll viewport (sticky, not fixed,
            so it only appears once there's actually something to scroll
            under it) and fades scrolled-past content out before it
            reaches the header, instead of the header hard-clipping it.
            The negative bottom margin matches its own height so it
            doesn't reserve scroll space -- it overlays the content
            that's already there rather than pushing it down. */}
        <div
          aria-hidden
          className="pointer-events-none sticky top-0 z-10 -mb-[101px] h-[101px] shrink-0 backdrop-blur-[2px] sm:hidden"
          style={{
            backgroundImage:
              "linear-gradient(180deg, rgba(255,255,255,0) 9%, rgba(255,255,255,1) 50%)",
          }}
        />
        {showEmpty ? (
          // "Full bleed" per the Figma reference: fixed to the viewport
          // (not the scrolling content column) and behind everything, so
          // it spans the whole window edge-to-edge horizontally -- the
          // sidebar's own opaque background naturally masks the portion
          // behind it. At this camera zoom the sphere's texture fills the
          // whole canvas edge-to-edge (no natural circular silhouette /
          // vignette to fade against), so oversizing+shifting the canvas
          // just moved a hard rectangular edge around instead of hiding
          // it. A CSS mask fading the canvas's own top edge to transparent
          // gives a soft top regardless of what the shader renders there.
          // Shifted down by half its own height so only the top half of
          // the sphere sits above the fold -- the rest is pushed below
          // the viewport's bottom edge rather than fully visible on screen.
          // Horizontally centered on the actual measured content column
          // (gradientBox, from the ResizeObserver above) rather than a
          // guessed sidebar-width offset -- stays correct regardless of
          // sidebar width or viewport size. Widened 200px total (100px
          // past each edge of that column) while keeping the same center.
          <GradientBackground
            className={`pointer-events-none fixed -bottom-[38vh] -z-10 hidden h-[75vh] transition-opacity duration-300 sm:block ${
              fadingOut || !gradientBox ? "opacity-0" : "opacity-100"
            }`}
            style={{
              left: gradientBox ? `${gradientBox.left}px` : undefined,
              width: gradientBox ? `${gradientBox.width}px` : undefined,
              maskImage: "linear-gradient(to bottom, transparent 0%, black 35%)",
              WebkitMaskImage: "linear-gradient(to bottom, transparent 0%, black 35%)",
            }}
          />
        ) : null}
        <div
          ref={contentColumnRef}
          className="relative mx-auto flex w-full max-w-[900px] flex-1 flex-col px-4 pb-10 pt-6 sm:px-0"
        >
        {showEmpty ? (
          <div
            className={`flex flex-1 -translate-y-[100px] flex-col items-center justify-center gap-6 text-center transition-opacity duration-300 ${
              fadingOut ? "opacity-0" : "opacity-100"
            }`}
            onTransitionEnd={() => {
              if (fadingOut) {
                setShowEmpty(false);
                setFadingOut(false);
              }
            }}
          >
            {/* Greeting slider (Figma node 96-2349): messages rotate every
                5s, a fixed box size (matching the Figma frame) keeps the
                bubble from resizing as shorter/taller messages rotate
                in, and the dots + tail mirror the reference. Only one
                message is ever rendered -- it slides out, THEN the next
                one slides in (see the greetingPhase effect above), so
                they never overlap. Desktop only -- the mobile empty-state
                frame (Figma node 121:3667) omits this bubble entirely. */}
            <div className="relative hidden h-[112px] w-[386px] max-w-full overflow-hidden rounded-[20px] bg-chat-warm sm:block">
              <p
                key={`${greetingIndex}-${greetingPhase}`}
                className={`absolute left-1/2 top-1/2 w-[342px] max-w-[calc(100%-44px)] text-center text-[16px] leading-[26px] text-chat-ink-soft ${
                  greetingPhase === "out" ? "greeting-slide-out" : "greeting-slide-in"
                }`}
              >
                {GREETING_MESSAGES[greetingIndex]}
              </p>
              <div className="absolute bottom-4 left-1/2 flex -translate-x-1/2 items-center gap-1">
                {GREETING_MESSAGES.map((message, i) => (
                  <span
                    key={message}
                    className={`rounded-full transition-all duration-500 ${
                      i === greetingIndex ? "h-2 w-2 bg-chat-accent-strong" : "h-1.5 w-1.5 bg-chat-border-warm"
                    }`}
                  />
                ))}
              </div>
              {/* The exported asset itself points up -- Figma's own
                  reference applies this same vertical flip to point it
                  down at the orb below. */}
              <img
                src="/icons/bubble-tail.svg"
                alt=""
                className="absolute -bottom-[10px] left-1/2 h-[11px] w-[21px] -translate-x-1/2 -scale-y-100"
              />
            </div>
            {/* Same looping video as apps/website's hero (and the auth
                pages' social-loading state) instead of the static AiOrb --
                same 112.5px slot size the orb used. */}
            {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
            <video
              src="/videos/social-loading.mp4"
              autoPlay
              loop
              muted
              playsInline
              className="h-[136.5px] w-[136.5px] shrink-0 rounded-full object-cover sm:h-[112.5px] sm:w-[112.5px]"
            />
            <h1 className="font-display max-w-[652px] text-[26px] font-medium text-chat-ink">
              Create, build, research or work with{" "}
              <span className="text-chat-accent-strong">less tokens</span>
            </h1>

            <div className="-mt-[10px] w-full max-w-[676px]">
              <Composer
                value={taskText}
                onChange={setTaskText}
                onSubmit={() => submit(taskText, modelPreference)}
                onCancel={cancelActive}
                running={running}
                cancelling={cancelling}
                placeholder="Ask me anything you want to do today!"
                modelPreference={modelPreference}
                onModelChange={setModelPreference}
              />
            </div>

            {/* Desktop only -- the mobile empty-state frame (Figma node
                121:3667) has no suggestion chips below the composer. */}
            <div className="hidden items-center gap-2.5 text-[14px] text-chat-ink sm:flex">
              <span>Start with</span>
              <div className="flex flex-wrap items-center justify-center gap-1">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s.label}
                    type="button"
                    onClick={() => setTaskText(s.prompt)}
                    className="group flex h-[30px] items-center gap-1 rounded-pill border border-chat-warm bg-chat-warm px-[6px] py-px text-[14px] text-chat-label hover:border-chat-border-warm hover:bg-chat-warm-hover hover:text-chat-ink active:border-chat-border-warm active:bg-chat-border-warm active:text-chat-ink"
                  >
                    {/* Two stacked icon assets (brown default, dark active) --
                        the SVGs' own hardcoded fill can't follow the text
                        color transition above, so both variants render and
                        opacity swaps on hover/active instead. */}
                    <span className="relative h-3.5 w-3.5">
                      <img
                        src={s.icon}
                        alt=""
                        className="absolute inset-0 h-3.5 w-3.5 group-hover:opacity-0 group-active:opacity-0"
                      />
                      <img
                        src={s.icon.replace(".svg", "-active.svg")}
                        alt=""
                        className="absolute inset-0 h-3.5 w-3.5 opacity-0 group-hover:opacity-100 group-active:opacity-100"
                      />
                    </span>
                    {s.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <>
            {/* chat-thread-in animates opacity+translateY on mount (see
                app/globals.css) -- kept off the composer below since a
                transform on any ancestor of a `sticky` element breaks its
                sticky positioning for the animation's duration. */}
            <div className="chat-thread-in flex flex-1 flex-col gap-10 pb-6">
              {turns.map((turn) => (
                <TurnBubble
                  key={turn.id}
                  job={turn}
                  events={turn.id === activeJobId ? activeEvents : []}
                  isActive={turn.id === activeJobId}
                  partialText={turn.id === activeJobId ? activePartialText : ""}
                  modelPreference={modelPreference}
                  onSwitchModel={(model) => submit(turn.task_text, model)}
                  onRegenerate={() => regenerateActive(turn.id)}
                />
              ))}
              <div ref={bottomRef} />
            </div>

            <div className="sticky bottom-0 bg-page pb-[30px]">
              {/* Fades scrolled-past turn text into the page background
                  before it reaches the composer, instead of the text
                  being hard-clipped behind it -- sits inside the sticky
                  wrapper so it stays pinned with the composer. The
                  wrapper itself carries a solid page-color pb-[30px]
                  (instead of just offsetting the composer by 30px) so
                  there's no gap below the composer where unfaded turn
                  text could still peek through. */}
              <div className="pointer-events-none absolute inset-x-0 -top-16 h-16 bg-gradient-to-b from-transparent to-page" />
              <Composer
                value={taskText}
                onChange={setTaskText}
                onSubmit={() => submit(taskText, modelPreference)}
                onCancel={cancelActive}
                running={running}
                cancelling={cancelling}
                placeholder="Write message"
                modelPreference={modelPreference}
                onModelChange={setModelPreference}
                variant="secondary"
              />
            </div>
          </>
        )}

        {error ? <p className="mt-3 text-[13.5px] text-critical">{error}</p> : null}
        </div>
      </div>
    </div>
  );
}
