"""Trace locale d'un agent : chaque décision du modèle et chaque appel de tool, avec arguments, résultat, durée et tokens."""
import time

import pandas as pd
from langchain_core.callbacks import BaseCallbackHandler


class Tracer(BaseCallbackHandler):
    """Callback à passer dans `config={"callbacks": [tracer]}` : chaque étape s'ajoute à `steps`."""

    def __init__(self):
        self.steps = []
        self._starts = {}
        self._pending = {}

    def on_chat_model_start(self, serialized, messages, *, run_id, **kwargs):
        self._starts[run_id] = time.time()

    def on_llm_end(self, response, *, run_id, **kwargs):
        message = response.generations[0][0].message
        usage = getattr(message, "usage_metadata", None) or {}
        calls = [c["name"] for c in message.tool_calls]
        self.steps.append({"type": "model", "name": "model", "decision": ", ".join(calls) or "réponse", "args": {}, "result": "", "calls": calls,
                           "seconds": round(time.time() - self._starts.pop(run_id, time.time()), 2),
                           "tokens": usage.get("total_tokens")})

    def on_tool_start(self, serialized, input_str, *, run_id, inputs=None, **kwargs):
        self._starts[run_id] = time.time()
        self._pending[run_id] = {"type": "tool", "name": serialized["name"], "decision": "", "args": dict(inputs or {})}

    def on_tool_end(self, output, *, run_id, **kwargs):
        content = getattr(output, "content", output)
        self.steps.append({**self._pending.pop(run_id), "result": str(content), "seconds": round(time.time() - self._starts.pop(run_id, time.time()), 2),
                           "tokens": None})

    def on_tool_error(self, error, *, run_id, **kwargs):
        self.steps.append({**self._pending.pop(run_id), "result": f"ERREUR {error}", "seconds": round(time.time() - self._starts.pop(run_id, time.time()), 2),
                           "tokens": None})

    def tool_calls(self):
        """Les appels de tools, dans l'ordre : name, args, result."""
        return [s for s in self.steps if s["type"] == "tool"]

    def decisions(self):
        """Pour chaque appel du modèle, la liste des tools demandés (vide pour la réponse finale)."""
        return [s["calls"] for s in self.steps if s["type"] == "model"]

    def table(self):
        """Les étapes en tableau, une ligne par décision du modèle ou appel de tool."""
        rows = [{"étape": i + 1, "type": s["type"], "tool ou décision": s["name"] if s["type"] == "tool" else s["decision"],
                 "arguments": str(s["args"])[:80], "résultat": s["result"][:60], "secondes": s["seconds"], "tokens": s["tokens"]}
                for i, s in enumerate(self.steps)]
        return pd.DataFrame(rows)
