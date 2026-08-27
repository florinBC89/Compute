// Baseline / Actual / Avoided is always derivable from what the API already
// returns (actual + avoided = baseline) -- no separate "baseline" endpoint,
// so every screen computes it the same way from the same two numbers.

export function ratio(avoided: number, baseline: number): number {
  return baseline > 0 ? avoided / baseline : 0;
}

export interface BaselineActualAvoided {
  baseline: number;
  actual: number;
  avoided: number;
  avoidedRatio: number;
}

export function tokenEconomics(consumed: number, avoided: number): BaselineActualAvoided {
  const baseline = consumed + avoided;
  return { baseline, actual: consumed, avoided, avoidedRatio: ratio(avoided, baseline) };
}

export function costEconomics(actual: number, avoided: number): BaselineActualAvoided {
  const baseline = actual + avoided;
  return { baseline, actual, avoided, avoidedRatio: ratio(avoided, baseline) };
}
