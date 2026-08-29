"use client";

// Phase 9: "Auto - Best value" is the spec's own mockup default -- routes
// each step to a different provider via app.agent.pipeline.AUTO_ROUTING
// server-side. The explicit 3-way choice from Phase 7 remains for anyone
// who wants one provider for the whole run.
export const MODEL_OPTIONS: { value: string; label: string }[] = [
  { value: "auto", label: "Auto - Best value" },
  { value: "openai", label: "GPT-4o mini" },
  { value: "anthropic", label: "Claude Haiku 4.5" },
  { value: "gemini", label: "Gemini 3.6 Flash" },
];

// The composer from the V0.3 Figma design ("Registered user" flow) --
// used both in the empty state ("Ask me anything...") and pinned under a
// populated thread ("Write message"), matching the same 20px-radius warm
// card in both places, just with different placeholder copy.
export default function Composer({
  value,
  onChange,
  onSubmit,
  onCancel,
  running,
  placeholder,
  modelPreference,
  onModelChange,
}: {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onCancel: () => void;
  running: boolean;
  placeholder: string;
  modelPreference: string;
  onModelChange: (value: string) => void;
}) {
  const selectedModel = MODEL_OPTIONS.find((m) => m.value === modelPreference);

  return (
    <div className="w-full rounded-[20px] bg-chat-warm px-[11px] py-[10px]">
      <div className="flex items-start justify-between gap-3">
        <textarea
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
          rows={1}
          className="min-h-[26px] flex-1 resize-none bg-transparent text-[16px] font-medium text-chat-ink placeholder:text-chat-ink outline-none disabled:opacity-70"
        />
        <button
          type="button"
          disabled
          title="Attaching files isn't available yet"
          className="flex shrink-0 items-center gap-0.5 rounded-pill border border-chat-border-warm px-[6px] py-[1px] text-[14px] text-chat-label opacity-70"
        >
          <img src="/icons/attach.svg" alt="" className="h-[18px] w-[18px]" />
          Attach files
        </button>
      </div>

      <div className="mt-3.5 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className="text-[14px] text-chat-label">Choose model</span>
          <div className="relative">
            <select
              value={modelPreference}
              onChange={(e) => onModelChange(e.target.value)}
              disabled={running}
              className="appearance-none rounded-pill border border-chat-border-warm bg-transparent py-[1px] pl-[8px] pr-[24px] text-[14px] text-chat-ink outline-none disabled:opacity-70"
            >
              {MODEL_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <img
              src="/icons/chevron-down.svg"
              alt=""
              className="pointer-events-none absolute right-[8px] top-1/2 h-[5.5px] w-[9.5px] -translate-y-1/2"
            />
          </div>
        </div>

        {running ? (
          <button
            type="button"
            onClick={onCancel}
            className="rounded-pill border border-chat-border-warm px-4 py-1.5 text-[14px] font-semibold text-chat-ink-soft"
          >
            Stop
          </button>
        ) : (
          <button
            type="button"
            onClick={onSubmit}
            disabled={!value.trim()}
            className="flex items-center gap-1.5 rounded-pill bg-accent px-4 py-1.5 text-[14px] font-semibold text-white disabled:opacity-40"
          >
            {selectedModel?.value === "openai" ? (
              <img src="/icons/model-openai.png" alt="" className="h-4 w-4 rounded-full" />
            ) : null}
            Send
          </button>
        )}
      </div>
    </div>
  );
}
