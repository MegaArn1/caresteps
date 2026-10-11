"""Model layer.

Two entry points:

* ``orchestrator.run_turn`` - the whole pipeline for one user message.
* ``provider.get_provider`` - the raw client, used only by the orchestrator.

The separation matters: nothing outside this package should be able to make a model
call, so the set of places a prompt can be sent from is exactly one module.
"""

from .orchestrator import TurnResult, orchestrator_metadata, run_turn
from .provider import LLMResult, Provider, get_provider

__all__ = [
    "LLMResult",
    "Provider",
    "TurnResult",
    "get_provider",
    "orchestrator_metadata",
    "run_turn",
]
