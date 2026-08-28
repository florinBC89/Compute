"use client";

import { useFormState, useFormStatus } from "react-dom";
import { signInWithMagicLink, type LoginState } from "./actions";

const initialState: LoginState = { status: "idle" };

function SubmitButton() {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      disabled={pending}
      className="rounded-pill bg-accent px-5 py-2.5 text-[14px] font-semibold text-white transition-opacity disabled:opacity-60"
    >
      {pending ? "Sending link…" : "Send sign-in link"}
    </button>
  );
}

export default function LoginPage() {
  const [state, formAction] = useFormState(signInWithMagicLink, initialState);

  return (
    <div className="flex min-h-[70vh] flex-col items-center justify-center">
      <div className="w-full max-w-[380px] rounded-card bg-surface p-8 shadow-card">
        <h1 className="text-[22px] font-semibold text-ink">Accurate</h1>
        <p className="mt-2 text-[14px] text-ink-secondary">
          Sign in with your email — no password to remember.
        </p>

        <form action={formAction} className="mt-6 flex flex-col gap-3">
          <input
            type="email"
            name="email"
            required
            placeholder="you@example.com"
            className="rounded-2xl border border-border bg-page px-4 py-2.5 text-[14px] text-ink outline-none focus:border-accent"
          />
          <SubmitButton />
        </form>

        {state.status === "sent" ? (
          <p className="mt-4 text-[13.5px] text-good">{state.message}</p>
        ) : null}
        {state.status === "error" ? (
          <p className="mt-4 text-[13.5px] text-critical">{state.message}</p>
        ) : null}
      </div>
    </div>
  );
}
