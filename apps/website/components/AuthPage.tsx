"use client";

import { useState } from "react";
import AuthForm from "./AuthForm";
import AuthPageLayout from "./AuthPageLayout";

// AuthPageLayout's decorated panel (gradient/bubble/orb) lives one level up
// from AuthForm, which is where the social-loading state is. Hoisting that
// one piece of state here (instead of AuthForm owning it) lets the layout
// drop to a single centered column -- same as reset-password's
// decorated={false} -- while the loading video is showing, rather than
// leaving the gradient rectangle sitting there next to it.
export default function AuthPage({ mode }: { mode: "signup" | "signin" }) {
  const [socialLoading, setSocialLoading] = useState(false);

  return (
    <AuthPageLayout decorated={!socialLoading} showLogo={!socialLoading}>
      <AuthForm mode={mode} socialLoading={socialLoading} setSocialLoading={setSocialLoading} />
    </AuthPageLayout>
  );
}
