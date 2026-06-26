import { useTheme } from "../shared/theme";

export function Framework() {
  const { clean } = useTheme();
  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-surface-border bg-surface-raised p-5 glow-card">
        <h2 className="text-lg font-bold text-slate-200 mb-1">{clean("🔬 Why CrewAI?")}</h2>
        <p className="text-sm text-slate-400">
          MAADS requires <em>role-differentiated</em>, <em>sequential</em>, <em>tool-using</em> agents
          that share state without chatting freely — exactly the regime CrewAI was designed for.
          Below is the evidence-grounded case, tied to peer-reviewed literature.
        </p>
      </div>

      {/* Design requirements */}
      <div className="rounded-2xl border border-surface-border bg-surface-raised p-5 glow-card">
        <h3 className="text-sm font-bold text-slate-300 mb-3">{clean("🎯 Our Hard Requirements")}</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {[
            { req: "Role specialisation", why: "CRISP-DM phases have distinct expertise — mixing them in one prompt degrades output quality" },
            { req: "YAML-driven configuration", why: "Agent personas, goals, and task scaffolds must be version-controlled and readable by non-engineers" },
            { req: "Per-agent LLM tiering", why: "PM and DS use top-tier models; DE and Storyteller use mid-tier to stay cost-efficient" },
            { req: "Python tool execution", why: "Data pipeline steps (EDA, cleaning, modeling) must execute real code, not describe it" },
            { req: "Sequential substep dispatch", why: "CRISP-DM has strict ordering with conditional back-edges — a free-form chat loop cannot enforce it" },
            { req: "Structured JSON output", why: "State deltas must be schema-validated; free text cannot be mechanically applied to a Pydantic model" },
          ].map(({ req, why }) => (
            <div key={req} className="rounded-xl bg-surface p-3 border border-surface-border">
              <div className="text-xs font-bold text-fuchsia-300 mb-1">{req}</div>
              <div className="text-xs text-slate-400">{why}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Framework comparison */}
      <div className="rounded-2xl border border-surface-border bg-surface-raised p-5 glow-card overflow-x-auto">
        <h3 className="text-sm font-bold text-slate-300 mb-3">{clean("⚖️ Framework Comparison")}</h3>
        <table className="w-full text-xs border-collapse min-w-[560px]">
          <thead>
            <tr className="border-b border-surface-border text-left">
              <th className="pb-2 text-slate-400 font-semibold pr-4">Capability</th>
              <th className="pb-2 text-fuchsia-300 font-semibold pr-4">{clean("CrewAI ✓")}</th>
              <th className="pb-2 text-slate-500 font-semibold pr-4">AutoGen</th>
              <th className="pb-2 text-slate-500 font-semibold pr-4">LangGraph</th>
              <th className="pb-2 text-slate-500 font-semibold">MetaGPT</th>
            </tr>
          </thead>
          <tbody className="text-slate-300">
            {[
              ["YAML agent/task config", "✓ native", "✗", "✗", "partial"],
              ["Per-agent LLM override", "✓ agent-level", "✓", "✗ global", "✗"],
              ["Sequential + conditional flow", "✓ Crew + Flow", "partial", "✓ graph", "✓ fixed"],
              ["Python tool execution", "✓ first-class", "✓", "✓", "✓"],
              ["Structured JSON tasks", "✓ schema-guided", "partial", "requires glue", "✓"],
              ["Role-based backstories", "✓ native", "✓", "manual", "✓"],
              ["Minimal agent-to-agent chat", "✓ state-mediated", "✗ free chat", "✓", "partial"],
            ].map(([cap, crew, autogen, langgraph, metagpt]) => (
              <tr key={cap} className="border-b border-surface-border/40">
                <td className="py-2 pr-4 text-slate-400">{cap}</td>
                <td className="py-2 pr-4 text-green-400 font-medium">{clean(crew)}</td>
                <td className="py-2 pr-4 text-slate-500">{clean(autogen)}</td>
                <td className="py-2 pr-4 text-slate-500">{clean(langgraph)}</td>
                <td className="py-2 text-slate-500">{clean(metagpt)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Scientific basis */}
      <div className="rounded-2xl border border-surface-border bg-surface-raised p-5 glow-card">
        <h3 className="text-sm font-bold text-slate-300 mb-4">{clean("📚 Scientific Basis")}</h3>
        <div className="space-y-4">
          {[
            {
              cite: "Hong et al. (2024)",
              venue: "ICLR 2024",
              title: "MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework",
              arxiv: "arXiv:2308.00352",
              relevance:
                "Shows that assigning standardised professional roles to LLM agents and enforcing structured output contracts (SOPs) cuts hallucination and improves code quality compared to single-agent baselines. MAADS mirrors this: each agent has a fixed CRISP-DM role and returns a validated schema.",
              crewai: "CrewAI role= and goal= fields implement the SOP assignment. YAML tasks.yaml is the structured output contract.",
            },
            {
              cite: "Li et al. (2023)",
              venue: "NeurIPS 2023",
              title: "CAMEL: Communicative Agents for 'Mind' Exploration of Large Language Model Society",
              arxiv: "arXiv:2303.17760",
              relevance:
                "Demonstrates that role-playing agents with role-specific system prompts consistently outperform single-agent prompting on collaborative tasks. Finds that free-form multi-agent chat degrades on long tasks unless constrained by a task structure.",
              crewai: "CrewAI backstory= provides the system-prompt persona. Task sequencing replaces unbounded chat.",
            },
            {
              cite: "Wu et al. (2023)",
              venue: "arXiv (Microsoft Research)",
              title: "AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation",
              arxiv: "arXiv:2308.08155",
              relevance:
                "Establishes that tool-using multi-agent systems outperform single-agent tool use on complex coding and data tasks. Also shows that unstructured agent-to-agent conversation introduces coordination failures at scale.",
              crewai: "MAADS uses CrewAI tool execution (PythonExec, FileIO) per agent rather than allowing free agent-to-agent chat — precisely to avoid the coordination failures AutoGen documents.",
            },
            {
              cite: "Yao et al. (2023)",
              venue: "ICLR 2023",
              title: "ReAct: Synergizing Reasoning and Acting in Language Models",
              arxiv: "arXiv:2210.03629",
              relevance:
                "Introduces the Reason + Act loop: LLM reasoning interleaved with tool calls. The developer agent's debug loop (classify error → reason → generate fix → execute) is a direct instantiation of ReAct.",
              crewai: "CrewAI's agent execution model follows the ReAct pattern: each task description triggers observe → reason → act (tool call or output).",
            },
            {
              cite: "Martínez-Plumed et al. (2021)",
              venue: "Expert Systems with Applications, Elsevier (Vol. 165)",
              title: "CRISP-DM Twenty Years Later: From Data Mining Processes to Data Science Trajectories",
              arxiv: "DOI:10.1016/j.eswa.2020.113795",
              relevance:
                "Survey of 760 real-world CRISP-DM deployments. Finds that phase iteration (loops) is the most commonly skipped CRISP-DM feature and the primary cause of deployed-model underperformance. Confirms the need for a loop-aware, phased orchestration layer.",
              crewai: "MAADS's loop contours (A/B/C/D) and the PM's directive schema directly address the gap this paper identifies.",
            },
            {
              cite: "Chapman et al. (2000)",
              venue: "CRISP-DM 1.0 Special Interest Group",
              title: "CRISP-DM 1.0: Step-by-Step Data Mining Guide",
              arxiv: "NCR/SPSS/DaimlerChrysler",
              relevance:
                "The authoritative reference model. Defines the six phases, 24 generic tasks, and four back-edge loop contours that MAADS implements. Field names in CrispDMState map one-to-one to the CRISP-DM 1.0 output names.",
              crewai: "SUBSTEP_NAMES and SUBSTEP_OWNER in state.py follow the CRISP-DM 1.0 table exactly.",
            },
          ].map((paper) => (
            <div
              key={paper.cite}
              className="rounded-xl border border-surface-border bg-surface p-4"
            >
              <div className="flex flex-wrap items-baseline gap-2 mb-1">
                <span className="text-fuchsia-300 font-bold text-xs">{paper.cite}</span>
                <span className="text-slate-500 text-xs">{paper.venue}</span>
                <span className="text-slate-600 text-xs font-mono">{paper.arxiv}</span>
              </div>
              <div className="text-slate-300 text-xs font-medium italic mb-2">{paper.title}</div>
              <div className="text-slate-400 text-xs mb-2">
                <span className="text-slate-500 font-semibold">Relevance: </span>
                {paper.relevance}
              </div>
              <div className="text-xs text-pink-300/80">
                <span className="text-pink-400 font-semibold">In MAADS: </span>
                {paper.crewai}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* How CrewAI maps to our design */}
      <div className="rounded-2xl border border-surface-border bg-surface-raised p-5 glow-card">
        <h3 className="text-sm font-bold text-slate-300 mb-3">{clean("🗺️ CrewAI → MAADS Mapping")}</h3>
        <div className="space-y-2 text-xs">
          {[
            ["agents.yaml role / goal / backstory_file", "Agent persona and system prompt loaded at construction via agent_for()"],
            ["tasks.yaml substep_json template", "Per-substep task description rendered with compile_task_payload()"],
            ["Crew(agents=[agent], tasks=[task])", "One-shot crew per substep — no shared conversational history between calls"],
            ["agent.llm = build_llm(tier)", "PM and DS → top-tier; DE, Developer, Storyteller → mid-tier (MODEL_CODE for coding tasks)"],
            ["output.token_usage.total_tokens", "Folded into state.token_spend[agent] and token_spend_by_provider[provider]"],
            ["CrewKickoffError", "Caught at every call site; escalated to debug module or halts with clear reason"],
          ].map(([crewai, maads]) => (
            <div key={crewai} className="flex gap-3 items-start py-1.5 border-b border-surface-border/40">
              <code className="text-fuchsia-300 shrink-0 text-[11px] w-64">{crewai}</code>
              <span className="text-slate-400">{maads}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}