"""Cooperative shutdown on SIGINT (Ctrl+C).

First Ctrl+C sets a flag so the orchestrator can finish the current step and
run cleanup (status flush, trace export, final state). A second Ctrl+C raises
``KeyboardInterrupt`` for an immediate exit.
"""
from __future__ import annotations

import signal
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from maads.state import CrispDMState

INTERRUPT_HALT_REASON = "interrupted by user (Ctrl+C)"

_shutdown_requested = False
_handler_installed = False


def shutdown_requested() -> bool:
    return _shutdown_requested


def request_shutdown() -> None:
    global _shutdown_requested
    _shutdown_requested = True


def reset_shutdown_state() -> None:
    """Clear the shutdown flag (for tests)."""
    global _shutdown_requested
    _shutdown_requested = False


def install_sigint_handler() -> None:
    """Install a SIGINT handler that cooperates with :func:`shutdown_requested`."""
    global _handler_installed
    if _handler_installed:
        return

    def _handler(signum: int, frame) -> None:  # noqa: ARG001
        if _shutdown_requested:
            raise KeyboardInterrupt
        request_shutdown()
        print(
            "\nInterrupt received — finishing cleanup "
            "(press Ctrl+C again to force quit)…",
            file=sys.stderr,
        )

    signal.signal(signal.SIGINT, _handler)
    _handler_installed = True


def apply_interrupt_to_state(state: CrispDMState) -> str:
    """Mark *state* halted due to user interrupt; return the halt reason."""
    if not state.halted:
        state.halted = True
        state.halt_reason = INTERRUPT_HALT_REASON
        state.append_log("orchestrator", INTERRUPT_HALT_REASON, level="warn")
    return state.halt_reason or INTERRUPT_HALT_REASON
