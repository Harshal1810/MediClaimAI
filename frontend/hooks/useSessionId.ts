"use client";

import { useEffect, useState } from "react";
import { createSessionId } from "@/lib/session";

export function useSessionId() {
  const [sessionId, setSessionId] = useState<string | null>(null);

  useEffect(() => {
    try {
      const existing = sessionStorage.getItem("claims_session_id");
      if (existing) {
        setSessionId(existing);
        return;
      }
      const next = createSessionId();
      sessionStorage.setItem("claims_session_id", next);
      setSessionId(next);
    } catch {
      setSessionId(createSessionId());
    }
  }, []);

  return sessionId;
}
