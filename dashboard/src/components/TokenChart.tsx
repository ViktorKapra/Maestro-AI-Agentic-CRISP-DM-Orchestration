import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type {
  CommunicationRecord,
  CommunicationsSummary,
  TokenBudgetStatus,
} from "../shared/types";
import { useTheme } from "../shared/theme";

// Per-agent bar colours, one cohesive palette per theme.
const AGENT_COLORS: Record<"pink" | "biz", Record<string, string>> = {
  pink: {
    pm: "#d6409f", // rose-fuchsia
    domain: "#a855f7", // lavender-purple
    data_engineer: "#ec4899", // pink
    data_scientist: "#c084fc", // light lavender
    developer: "#f472b6", // bubblegum
    storyteller: "#e879f9", // orchid
  },
  biz: {
    pm: "#38bdf8", // sky
    domain: "#818cf8", // indigo
    data_engineer: "#22d3ee", // cyan
    data_scientist: "#34d399", // emerald
    developer: "#a78bfa", // violet
    storyteller: "#60a5fa", // blue
  },
};

// Full, human-readable agent names (shared by both themes).
const AGENT_NAMES: Record<string, string> = {
  pm: "Project Manager",
  domain: "Domain Expert",
  data_engineer: "Data Engineer",
  data_scientist: "Data Scientist",
  developer: "Developer",
  storyteller: "Storyteller",
};

// Chart chrome (grid, axes, tooltip, line) per theme.
const CHART_THEME = {
  pink: {
    fallbackBar: "#c9a9d6",
    grid: "#f1cde9",
    axis: "#a98fb8",
    tooltipBg: "#ffffff",
    tooltipBorder: "#f1cde9",
    tooltipText: "#3b1f47",
    line: "#d6409f",
  },
  biz: {
    fallbackBar: "#475569",
    grid: "#1e293b",
    axis: "#64748b",
    tooltipBg: "#0f172a",
    tooltipBorder: "#1e293b",
    tooltipText: "#e2e8f0",
    line: "#38bdf8",
  },
};

interface Props {
  summary: CommunicationsSummary | undefined;
  communications?: CommunicationRecord[] | undefined;
  tokenSpend: Record<string, number> | undefined;
  tokenBudget?: TokenBudgetStatus;
}

export function TokenChart({ summary, communications, tokenSpend, tokenBudget }: Props) {
  const { theme, clean } = useTheme();
  const palette = AGENT_COLORS[theme];
  const c = CHART_THEME[theme];
  const barData = Object.entries(tokenSpend ?? {}).map(([agent, tokens]) => ({
    agent,
    name: AGENT_NAMES[agent] ?? agent,
    tokens,
    fill: palette[agent] ?? c.fallbackBar,
  }));

  const sparkData = (communications ?? [])
    .filter((c) => c.tokens?.total)
    .sort(
      (a, b) =>
        new Date(a.started_at).getTime() - new Date(b.started_at).getTime(),
    )
    .reduce<{ time: string; cumulative: number; turn: string }[]>(
      (acc, comm, i) => {
        const prev = acc[i - 1]?.cumulative ?? 0;
        acc.push({
          time: new Date(comm.started_at).toLocaleTimeString(),
          cumulative: prev + (comm.tokens.total ?? 0),
          turn: comm.id,
        });
        return acc;
      },
      [],
    );

  const total =
    summary?.total_tokens ??
    Object.values(tokenSpend ?? {}).reduce((a, b) => a + b, 0);
  const cap = tokenBudget?.cap ?? null;
  const remaining = tokenBudget?.remaining ?? null;
  const nearCap = Boolean(
    tokenBudget?.soft_limit ||
      (tokenBudget?.pct != null && tokenBudget.pct >= (tokenBudget.soft_limit_pct ?? 90)),
  );

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm text-slate-400 mb-1 font-semibold">
          {clean("💎 Total tokens")}
        </p>
        <p
          className={`text-3xl font-bold tabular-nums ${
            nearCap ? "text-amber-400" : "text-accent"
          }`}
        >
          {total.toLocaleString()}
        </p>
        {cap != null && (
          <p className={`text-sm mt-1 ${nearCap ? "text-amber-400/90" : "text-slate-400"}`}>
            Budget: {total.toLocaleString()} / {cap.toLocaleString()}
            {remaining != null ? ` (${remaining.toLocaleString()} remaining` : ""}
            {tokenBudget?.pct != null ? `, ${tokenBudget.pct}%` : ""}
            {remaining != null ? ")" : ""}
            {tokenBudget?.soft_limit ? " · soft limit active" : ""}
          </p>
        )}
        {summary && (
          <p className="text-xs text-slate-500 mt-1">
            {clean("💌")} {summary.turn_count} LLM turns · avg{" "}
            {Math.round(summary.avg_duration_ms / 1000)}s per turn
          </p>
        )}
      </div>

      {barData.length > 0 && (
        <div>
          <p className="text-sm text-slate-400 mb-2 font-semibold">
            {clean("👯 By agent")}
          </p>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={barData} layout="vertical" margin={{ left: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={c.grid} />
              <XAxis type="number" tick={{ fill: c.axis, fontSize: 11 }} />
              <YAxis
                type="category"
                dataKey="name"
                width={120}
                tick={{ fill: c.axis, fontSize: 11 }}
              />
              <Tooltip
                contentStyle={{
                  background: c.tooltipBg,
                  border: `1px solid ${c.tooltipBorder}`,
                  borderRadius: 8,
                }}
                labelStyle={{ color: c.tooltipText, fontWeight: 600 }}
                itemStyle={{ color: c.tooltipText }}
              />
              <Bar dataKey="tokens" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {sparkData.length > 1 && (
        <div>
          <p className="text-sm text-slate-400 mb-2 font-semibold">
            {clean("📈 Cumulative spend")}
          </p>
          <ResponsiveContainer width="100%" height={120}>
            <LineChart data={sparkData}>
              <CartesianGrid strokeDasharray="3 3" stroke={c.grid} />
              <XAxis dataKey="time" tick={{ fill: c.axis, fontSize: 10 }} />
              <YAxis tick={{ fill: c.axis, fontSize: 10 }} />
              <Tooltip
                contentStyle={{
                  background: c.tooltipBg,
                  border: `1px solid ${c.tooltipBorder}`,
                  borderRadius: 8,
                }}
                labelStyle={{ color: c.tooltipText, fontWeight: 600 }}
                itemStyle={{ color: c.tooltipText }}
              />
              <Line
                type="monotone"
                dataKey="cumulative"
                stroke={c.line}
                dot={false}
                strokeWidth={2}
              />
              {cap != null && (
                <ReferenceLine
                  y={cap}
                  stroke={nearCap ? "#fbbf24" : "#94a3b8"}
                  strokeDasharray="4 4"
                  label={{
                    value: `cap ${cap.toLocaleString()}`,
                    fill: nearCap ? "#fbbf24" : c.axis,
                    fontSize: 10,
                    position: "insideTopRight",
                  }}
                />
              )}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
