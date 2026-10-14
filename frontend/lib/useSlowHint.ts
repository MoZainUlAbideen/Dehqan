"use client";

import { useEffect, useState } from "react";

/** True once `active` has stayed true for `ms`. Used to explain a slow first request (free hosting wakes from sleep). */
export function useSlowHint(active: boolean, ms = 6000): boolean {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    if (!active) return;
    const timer = setTimeout(() => setSlow(true), ms);
    return () => {
      clearTimeout(timer);
      setSlow(false);
    };
  }, [active, ms]);
  return active && slow;
}

export const WAKING_MESSAGE =
  "Still working… the free server goes to sleep when nobody uses it, and waking it up can take up to a minute. Thanks for waiting.";
