"use client";

import { useEffect, useState } from "react";

//: iOS Safari doesn't resize the LAYOUT viewport when the on-screen
//: keyboard opens -- only the VISUAL viewport (what's actually visible)
//: shrinks. A `position: sticky`/`fixed` bottom-pinned element is still
//: genuinely "stuck" from CSS's point of view, but it's stuck to the
//: bottom of the full layout viewport, which the keyboard now covers --
//: from the user's side, it reads as "the composer scrolled away under
//: the keyboard" even though nothing actually un-stuck it. `visualViewport`
//: is the one API that reports the real, currently-visible area, so this
//: tracks it and returns how many px of the layout viewport's bottom are
//: currently covered (keyboard height + any pan offset) -- 0 whenever the
//: keyboard's closed or the API isn't supported, so callers can use it as
//: a pure `transform: translateY(-coverage)` nudge with no effect at all
//: in the common case.
export function useKeyboardCoverage(): number {
  const [coverage, setCoverage] = useState(0);

  useEffect(() => {
    const vv = window.visualViewport;
    if (!vv) return;

    function update() {
      const covered = window.innerHeight - vv!.height - vv!.offsetTop;
      setCoverage(Math.max(0, Math.round(covered)));
    }

    update();
    vv.addEventListener("resize", update);
    vv.addEventListener("scroll", update);
    return () => {
      vv.removeEventListener("resize", update);
      vv.removeEventListener("scroll", update);
    };
  }, []);

  return coverage;
}
