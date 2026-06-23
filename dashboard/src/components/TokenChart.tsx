import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { CommunicationRecord, CommunicationsSummary } from "../shared/types";

const AGENT_COLORS: Record<string, string> = {
  pm: "#3b82f6",
  domain: "#8b5cf6",
  data_engineer: "#06b6d4",
  data_scientist: "#f59e0b",
  developer: "#22c55e",
};

interface Props {
  summary: CommunicationsSummary | undefined;
  communications: CommunicationRecord[] | undefined;
  tokenSpend: Record<string, number> | undefined;
}

export function TokenChart({ summary, communications, tokenSpend }: Props) {
  const barData = Object.entries(tokenSpend ?? {}).map(([agent, tokens]) => ({
    agent,
    tokens,
    fill: AGENT_COLORS[agent] ?? "#64748b",
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

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm text-slate-400 mb-1">Total tokens</p>
        <p className="text-3xl font-semibold tabular-nums">
          {total.toLocaleString()}
        </p>
        {summary && (
          <p className="text-xs text-slate-500 mt-1">
            {summary.turn_count} LLM turns · avg{" "}
            {Math.round(summary.avg_duration_ms / 1000)}s per turn
          </p>
        )}
      </div>

      {barData.length > 0 && (
        <div>
          <p className="text-sm text-slate-400 mb-2">By agent</p>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={barData} layout="vertical" margin={{ left: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2d3a4f" />
              <XAxis type="number" tick={{ fill: "#94a3b8", fontSize: 11 }} />
              <YAxis
                type="category"
                dataKey="agent"
                width={100}
                tick={{ fill: "#94a3b8", fontSize: 11 }}
              />
              <Tooltip
                contentStyle={{
                  background: "#1a2332",
                  border: "1px solid #2d3a4f",
                  borderRadius: 8,
                }}
              />
              <Bar dataKey="tokens" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {sparkData.length > 1 && (
        <div>
          <p className="text-sm text-slate-400 mb-2">Cumulative spend</p>
          <ResponsiveContainer width="100%" height={120}>
            <LineChart data={sparkData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2d3a4f" />
              <XAxis dataKey="time" tick={{ fill: "#94a3b8", fontSize: 10 }} />
              <YAxis tick={{ fill: "#94a3b8", fontSize: 10 }} />
              <Tooltip
                contentStyle={{
                  background: "#1a2332",
                  border: "1px solid #2d3a4f",
                  borderRadius: 8,
                }}
              />
              <Line
                type="monotone"
                dataKey="cumulative"
                stroke="#60a5fa"
                dot={false}
                strokeWidth={2}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
