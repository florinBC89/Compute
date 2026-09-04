"use client";

import { useEffect, useRef, useState } from "react";

// Phase 9: "Auto - Best value" is the spec's own mockup default -- routes
// each step to a different provider via app.agent.pipeline.AUTO_ROUTING
// server-side. The explicit 3-way choice from Phase 7 remains for anyone
// who wants one provider for the whole run. Icons are only set where a
// real exported asset exists (Auto/Gemini have none -- not fabricated).
export const MODEL_OPTIONS: { value: string; label: string; icon?: string }[] = [
  { value: "auto", label: "Auto - Best value" },
  { value: "openai", label: "GPT-4o mini", icon: "/icons/model-openai.png" },
  { value: "anthropic", label: "Claude Haiku 4.5", icon: "/icons/model-anthropic.png" },
  { value: "gemini", label: "Gemini 3.6 Flash" },
];

//: content viewport max-height before the composer switches from
//: auto-grow to internal scroll (Figma's "scroll option appears" state) --
//: distinct per composer size, since the fixed 36px action row + insets
//: eat proportionally more of the smaller frame:
//: primary (676px, empty state, 302px max frame): action row top 254px,
//:   11px top inset -> 254 - 11 = 243px.
//: secondary (900px, populated, 276px max frame): action row top 228px,
//:   11px top inset -> 228 - 11 = 217px.
const TEXTAREA_MAX_HEIGHT = { primary: 243, secondary: 217 } as const;

function ModelDropdown({
  value,
  onChange,
  disabled,
}: {
  value: string;
  onChange: (value: string) => void;
  disabled: boolean;
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const selected = MODEL_OPTIONS.find((m) => m.value === value) ?? MODEL_OPTIONS[0];

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  return (
    <div ref={rootRef} className="relative flex items-center gap-2.5">
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((v) => !v)}
        className={`flex items-center gap-1 whitespace-nowrap text-[14px] hover:text-chat-ink disabled:opacity-70 ${
          open ? "text-chat-ink" : "text-chat-label"
        }`}
      >
        Choose model
        <img
          src="/icons/chevron-down.svg"
          alt=""
          className={`h-[5.5px] w-[9.5px] transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-0.5 whitespace-nowrap rounded-pill border border-chat-border-warm bg-surface py-[1px] pl-[7px] pr-[8px] text-[14px] text-chat-ink hover:bg-chat-warm active:bg-chat-border-warm disabled:opacity-70"
      >
        {selected.icon ? (
          <img src={selected.icon} alt="" className="h-4 w-4 rounded-full" />
        ) : null}
        {selected.label}
      </button>

      {open ? (
        <div className="absolute bottom-full right-0 mb-2 w-[225px] rounded-[15px] border border-chat-border-warm bg-chat-warm p-[5px]">
          <ul className="flex flex-col gap-0.5">
            {MODEL_OPTIONS.map((option) => (
              <li key={option.value}>
                <button
                  type="button"
                  onClick={() => {
                    onChange(option.value);
                    setOpen(false);
                  }}
                  className="flex w-full items-center gap-1 rounded-[10px] bg-surface px-2 py-1.5 text-left text-[15px] text-chat-ink"
                >
                  {option.icon ? (
                    <img src={option.icon} alt="" className="h-4 w-4 rounded-full" />
                  ) : (
                    <span className="w-4" />
                  )}
                  {option.label}
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

// "Lazy" mode: appends a code-minimalism ruleset to this turn's system
// prompt (apps/api's app.agent.chat.LAZY_MODE_SYSTEM_SUFFIX) -- off by
// default, toggled per-turn right next to the model picker since it's the
// same kind of per-message choice. --accent-soft/--accent-track exist in
// app/globals.css specifically for a lit-up toggle state like this one but
// had no component using them yet.
function LazyToggle({
  active,
  onToggle,
  disabled,
}: {
  active: boolean;
  onToggle: () => void;
  disabled: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      disabled={disabled}
      title={
        active
          ? "Lazy mode is on -- code answers favor the smallest correct change"
          : "Lazy mode -- ask for lean, minimal code"
      }
      className={`flex items-center gap-1 rounded-pill border px-[7px] py-[1px] text-[14px] disabled:opacity-70 ${
        active
          ? "border-accent bg-accent-soft text-accent"
          : "border-chat-border-warm text-chat-label hover:bg-chat-warm hover:text-chat-ink"
      }`}
    >
      Lazy
    </button>
  );
}

// The composer from the V0.3 Figma design ("Registered user" flow, plus
// the "Chat primary/secondary component states" specs) -- used both in
// the empty state ("Ask me anything...") and pinned under a populated
// thread ("Write message"). Figma's raw Default/Active states show the
// model dropdown shifting position once the send button appears; that's
// deliberately overridden here -- the dropdown always sits in the same
// spot via a fixed-size reserved left slot, so it never jumps around as
// the user types.
export default function Composer({
  value,
  onChange,
  onSubmit,
  onCancel,
  running,
  cancelling = false,
  placeholder,
  modelPreference,
  onModelChange,
  lazyMode,
  onLazyModeChange,
  variant = "primary",
}: {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onCancel: () => void;
  running: boolean;
  //: True for the brief window between clicking Stop and the job actually
  //: stopping (up to ~0.5s server-side) -- disables the button so that
  //: gap doesn't invite a second click.
  cancelling?: boolean;
  placeholder: string;
  modelPreference: string;
  onModelChange: (value: string) => void;
  lazyMode: boolean;
  onLazyModeChange: (value: boolean) => void;
  //: "primary" = the 676px empty-state composer; "secondary" = the 900px
  //: composer pinned under a populated thread -- see TEXTAREA_MAX_HEIGHT.
  variant?: "primary" | "secondary";
}) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const hasContent = value.trim().length > 0;
  const maxHeight = TEXTAREA_MAX_HEIGHT[variant];
  //: Mobile only (see the sm: overrides below): while the keyboard's up,
  //: every row but the text input itself hides, so the composer collapses
  //: to just its own height instead of eating screen space the keyboard
  //: already claimed. Enter-to-submit (onKeyDown below) still works with
  //: the Send button hidden. Desktop has no keyboard to reclaim space
  //: from, so it always shows the full composer regardless of focus.
  const [isFocused, setIsFocused] = useState(false);
  const secondaryRowClass = isFocused ? "hidden sm:flex" : "flex";
  // The edge-fade mask (.chat-scroll) only makes sense once there's
  // actually something to scroll -- applied unconditionally, it would
  // fade the top/bottom of perfectly short, fully-visible text too.
  const [isScrollable, setIsScrollable] = useState(false);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, maxHeight)}px`;
    setIsScrollable(el.scrollHeight > maxHeight);
  }, [value, maxHeight]);

  return (
    <div className="w-full rounded-[20px] border border-chat-border-warm bg-chat-warm px-[11px] py-[10px]">
      <div className="flex items-start gap-3.5">
        <div className="relative flex-1">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                if (!running) onSubmit();
              }
            }}
            disabled={running}
            placeholder={placeholder}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            rows={1}
            // -mr-[5px]: pulls the textarea's own right edge 5px past the
            // composer's 11px padding, so its native scrollbar (which always
            // renders flush against the element's own box) lands ~6px from
            // the composer's true right edge instead of 11px, matching the
            // real Figma scroll-state frame (scrollbar ~7px from the outer
            // edge, ~8px past where the text itself stops).
            className="chat-scroll -mr-[5px] min-h-[26px] w-full resize-none overflow-y-auto bg-transparent pr-[8px] text-[16px] font-medium text-chat-ink placeholder:text-chat-ink outline-none disabled:opacity-70"
            style={{ maxHeight }}
          />
          {/* Fades the top/bottom of the TEXT to transparent, not the
              textarea itself -- a mask-image on the scrollable element
              would mask its native scrollbar too (confirmed: it faded
              out along with the text). These sit on top as a solid
              --chat-warm -> transparent gradient, inset far enough right
              (13px = 8px text padding + 5px scrollbar) to clear the
              scrollbar column entirely so it stays fully visible. */}
          {isScrollable ? (
            <>
              <div className="pointer-events-none absolute left-0 right-[13px] top-0 h-10 bg-gradient-to-b from-chat-warm via-chat-warm/70 to-transparent" />
              <div className="pointer-events-none absolute left-0 right-[13px] bottom-0 h-10 bg-gradient-to-t from-chat-warm via-chat-warm/70 to-transparent" />
            </>
          ) : null}
        </div>
        {/* Figma: the attach-files control is only present in the empty
            composer -- every Typing/Active/Expandable state has it hidden,
            since a real message has no room to also show attaching. */}
        {!hasContent ? (
          <button
            type="button"
            disabled
            title="Attaching files isn't available yet"
            className={`shrink-0 items-center gap-0.5 rounded-pill border border-chat-border-warm px-[6px] py-[1px] text-[14px] text-chat-border-warm ${secondaryRowClass}`}
          >
            <img src="/icons/attach-disabled.svg" alt="" className="h-[18px] w-[18px]" />
            Attach files
          </button>
        ) : null}
      </div>

      {/* flex-wrap: adding the Lazy toggle left this row too wide to fit
          Send/spacer + Lazy + "Choose model" + the current-model pill on
          one line at narrow mobile widths -- their text was wrapping
          mid-word inside each button instead ("Choose" / "model") rather
          than the row itself wrapping. ml-auto on the right-hand group
          (below) replaces justify-between here so that group still lands
          flush right whether it's sharing the first line or, once there's
          no room, dropped to a full-width line of its own -- same visual
          result as before on desktop/wide mobile, where it never needs to
          wrap at all. */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        {/* A fixed-size left slot, always reserved (empty when idle) so the
            model dropdown on the right never shifts position depending on
            whether Send/Stop is showing -- the dropdown must stay put
            regardless of composer content. Its own visibility is
            independent from the model dropdown's: once there's something
            to send (or a run to stop), the Send/Stop button stays visible
            even while focused on mobile -- only the truly-idle empty
            spacer hides there, matching Attach-files' own condition. */}
        <div className={`mt-3.5 ${running || hasContent ? "flex" : secondaryRowClass}`}>
          {running ? (
            // Same slot/size as the Send button below (h-9 w-9) so nothing
            // shifts when a run starts -- a filled circle with a solid
            // square reads as "stop" without needing its own icon asset.
            <button
              type="button"
              onClick={onCancel}
              disabled={cancelling}
              title={cancelling ? "Stopping…" : "Stop"}
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-accent hover:opacity-90 disabled:opacity-60"
            >
              <span className="h-3.5 w-3.5 rounded-[4px] bg-white" />
            </button>
          ) : hasContent ? (
            <button type="button" onClick={onSubmit} title="Send" className="shrink-0">
              <img src="/icons/send-active.svg" alt="Send" className="h-9 w-9" />
            </button>
          ) : (
            <span aria-hidden className="h-9 w-9 shrink-0" />
          )}
        </div>

        <div className={`mt-3.5 ml-auto flex items-center gap-2 ${secondaryRowClass}`}>
          <LazyToggle
            active={lazyMode}
            onToggle={() => onLazyModeChange(!lazyMode)}
            disabled={running}
          />
          <ModelDropdown value={modelPreference} onChange={onModelChange} disabled={running} />
        </div>
      </div>
    </div>
  );
}
