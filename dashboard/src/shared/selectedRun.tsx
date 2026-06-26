import { createContext, useContext, useState } from "react";
import type { ReactNode } from "react";

interface SelectedRunValue {
  /** The run_id the user is viewing, or null to follow the case's active run. */
  runId: string | null;
  setRunId: (id: string | null) => void;
}

const SelectedRunContext = createContext<SelectedRunValue | null>(null);

export function SelectedRunProvider({ children }: { children: ReactNode }) {
  const [runId, setRunId] = useState<string | null>(null);
  return (
    <SelectedRunContext.Provider value={{ runId, setRunId }}>
      {children}
    </SelectedRunContext.Provider>
  );
}

export function useSelectedRun(): SelectedRunValue {
  const ctx = useContext(SelectedRunContext);
  if (!ctx) throw new Error("useSelectedRun must be used within a SelectedRunProvider");
  return ctx;
}
