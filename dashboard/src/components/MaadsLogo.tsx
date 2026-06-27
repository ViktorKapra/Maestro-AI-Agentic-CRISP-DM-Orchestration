/**
 * MAADS mark — "Hex Mesh": a chip-like hexagon holding a small agent network,
 * a hub coordinating its team. Conveys multi-agent orchestration + workload.
 * Uses currentColor so it follows the active theme's accent (set via text-*).
 */
export function MaadsLogo({ className = "" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 48 48"
      className={className}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-label="MAADS"
      role="img"
    >
      {/* chip / node shell */}
      <polygon
        points="24,4 41.3,14 41.3,34 24,44 6.7,34 6.7,14"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinejoin="round"
      />
      {/* spokes from the hub to each agent */}
      <path
        d="M24 23 16 17M24 23 32 17M24 23 24 33"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        opacity="0.45"
      />
      {/* agent nodes */}
      <circle cx="16" cy="17" r="2.1" fill="currentColor" opacity="0.8" />
      <circle cx="32" cy="17" r="2.1" fill="currentColor" opacity="0.8" />
      <circle cx="24" cy="33" r="2.1" fill="currentColor" opacity="0.8" />
      {/* orchestrator hub */}
      <circle cx="24" cy="23" r="3.4" fill="currentColor" />
    </svg>
  );
}
