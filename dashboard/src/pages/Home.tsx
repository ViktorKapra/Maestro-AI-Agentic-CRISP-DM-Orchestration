import { useEffect, useRef, useState } from "react";
import { useTheme } from "../shared/theme";

interface Props {
  onLaunch: () => void;
  onExplore: () => void;
  datasetCount?: number;
  experimentCount?: number;
}

// Counts up from 0 to `target` once on mount; jumps straight to the value when
// the user prefers reduced motion.
function useCountUp(target: number, duration = 2400, delay = 450): number {
  const [value, setValue] = useState(0);
  const rafRef = useRef<number>();

  useEffect(() => {
    const reduce = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    if (reduce || target <= 0) {
      setValue(target);
      return;
    }
    const start = performance.now() + delay;
    const tick = (now: number) => {
      const t = Math.min(1, Math.max(0, now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3); // easeOutCubic
      setValue(Math.round(target * eased));
      if (t < 1) rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [target, duration, delay]);

  return value;
}

function Kpi({ value, label }: { value: number | string; label: string }) {
  const isNum = typeof value === "number";
  const animated = useCountUp(isNum ? value : 0);
  return (
    <div>
      <p className="text-4xl font-bold tracking-tight tabular-nums text-slate-100">
        {isNum ? animated.toLocaleString() : value}
      </p>
      <p className="mt-1 text-sm text-slate-400">{label}</p>
    </div>
  );
}

export function Home({
  onLaunch,
  onExplore,
  datasetCount,
  experimentCount,
}: Props) {
  const { clean } = useTheme();

  return (
    <div className="relative overflow-hidden">
      {/* cinematic accent glow behind the headline */}
      <div
        aria-hidden
        className="pointer-events-none absolute -top-24 left-1/4 h-[460px] w-[460px] -translate-x-1/2 rounded-full bg-accent/20 blur-[130px]"
      />

      <section className="relative max-w-5xl mx-auto pt-12 pb-2">
        <span
          className="reveal inline-flex items-center gap-2 rounded-full border border-surface-border bg-surface/60 px-4 py-1.5 text-xs font-semibold text-slate-400 backdrop-blur"
          style={{ animationDelay: "0ms" }}
        >
          <span className="h-2 w-2 rounded-full bg-accent node-active" />
          {clean("Multi-agent CRISP-DM · fully autonomous")}
        </span>

        <h1
          className="reveal mt-7 text-5xl font-bold leading-[1.04] tracking-tight text-slate-100 sm:text-6xl"
          style={{ animationDelay: "100ms" }}
        >
          Data science,
          <br />
          on{" "}
          <span className="bg-gradient-to-r from-fuchsia-500 via-pink-500 to-purple-500 bg-clip-text text-transparent">
            autopilot.
          </span>
        </h1>

        <p
          className="reveal mt-6 max-w-2xl text-lg leading-relaxed text-slate-400"
          style={{ animationDelay: "220ms" }}
        >
          Six specialized AI agents take a dataset through the entire CRISP-DM
          lifecycle — from business understanding and modeling to evaluation and
          a polished, ready-to-ship handoff.
        </p>
        <p
          className="reveal mt-3 max-w-2xl text-lg font-medium text-slate-300"
          style={{ animationDelay: "300ms" }}
        >
          You set the goal. The agents do the rest.
        </p>

        <div
          className="reveal mt-9 flex flex-wrap gap-4"
          style={{ animationDelay: "340ms" }}
        >
          <button
            type="button"
            onClick={onLaunch}
            className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-fuchsia-500 to-pink-500 px-6 py-3 text-sm font-semibold text-white shadow-md transition-all hover:scale-[1.03] hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-accent/50"
          >
            Launch an Experiment
            <span aria-hidden className="text-base leading-none">
              →
            </span>
          </button>
          <button
            type="button"
            onClick={onExplore}
            disabled={!experimentCount}
            title={
              !experimentCount ? "No experiments yet — launch one first" : undefined
            }
            className="inline-flex items-center rounded-xl border border-surface-border bg-surface/50 px-6 py-3 text-sm font-semibold text-slate-100 backdrop-blur transition-all hover:bg-surface-border focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-surface/50"
          >
            Explore a Run
          </button>
        </div>
      </section>

      <section
        className="reveal relative max-w-5xl mx-auto mt-16 border-t border-surface-border/60 pt-8"
        style={{ animationDelay: "460ms" }}
      >
        <div className="grid grid-cols-2 gap-8 sm:grid-cols-4">
          <Kpi value={datasetCount ?? "—"} label="Datasets tested" />
          <Kpi value={6} label="Specialized AI agents" />
          <Kpi value={experimentCount ?? "—"} label="Experiments run" />
          <Kpi value={24} label="CRISP-DM substeps" />
        </div>
      </section>
    </div>
  );
}
