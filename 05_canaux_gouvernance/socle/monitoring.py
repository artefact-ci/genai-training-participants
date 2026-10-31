"""Suivi de l'assistant en production : indicateurs techniques, coût par conversation, traces Langfuse (module partagé observability.py).

Deux familles d'indicateurs : techniques (latence, appels au modèle, outils appelés, tokens, coût) et métier
(résolution sans humain, transferts, conformité), que le service agrège dans `Metrics`.
"""
import json
import os
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Optional

from langchain_core.callbacks import BaseCallbackHandler

import guardrails  # noqa: F401  (ajoute code_partage au chemin d'import)
from observability import clear_langfuse, langfuse_callbacks, langfuse_enabled, pseudonym  # noqa: E402,F401  (traces Langfuse, optionnelles)

JOURNAL = Path(os.getenv("SUIVI_JOURNAL") or Path(tempfile.gettempdir()) / "lagune_suivi.jsonl")


class Tracker(BaseCallbackHandler):
    """Rappel LangChain (`config={"callbacks": [tracker]}`) : compte les appels au modèle, les tokens et les outils d'un tour."""

    def __init__(self):
        self.debut = time.time()
        self.appels_modele = 0
        self.tokens_entree = 0
        self.tokens_sortie = 0
        self.outils: list[str] = []

    def on_llm_end(self, response, **kw):
        msg = response.generations[0][0].message
        usage = getattr(msg, "usage_metadata", None) or {}
        self.appels_modele += 1
        self.tokens_entree += usage.get("input_tokens", 0)
        self.tokens_sortie += usage.get("output_tokens", 0)

    def on_tool_start(self, serialized, input_str, **kw):
        self.outils.append((serialized or {}).get("name") or kw.get("name") or "?")

    def report(self) -> dict:
        """Indicateurs du tour : latence, appels au modèle, tokens, outils."""
        return {"latence_s": round(time.time() - self.debut, 2), "appels_modele": self.appels_modele,
                "tokens_entree": self.tokens_entree, "tokens_sortie": self.tokens_sortie, "outils": list(self.outils)}


def cost(tokens_entree: int, tokens_sortie: int, prix_entree_par_million: float, prix_sortie_par_million: float) -> float:
    """Coût d'un appel (ou d'une conversation) : la tarification est distincte en entrée et en sortie."""
    return (tokens_entree * prix_entree_par_million + tokens_sortie * prix_sortie_par_million) / 1_000_000


def log_event(evenement: dict) -> None:
    """Une ligne JSON par tour de conversation. Aucun texte client : seulement des indicateurs."""
    with JOURNAL.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"t": round(time.time()), **evenement}, ensure_ascii=False) + "\n")


def read_log() -> list[dict]:
    """Relit le journal : une entrée par tour."""
    if not JOURNAL.exists():
        return []
    return [json.loads(ligne) for ligne in JOURNAL.read_text(encoding="utf-8").splitlines() if ligne.strip()]


class Metrics:
    """Compteurs agrégés, exposés par GET /metriques."""

    def __init__(self):
        self.c = Counter()
        self.latences: list[float] = []

    def record(self, category: Optional[str], report: dict, transfert: bool, bloque: bool):
        self.c["tours"] += 1
        self.c[f"categorie_{category or 'inconnue'}"] += 1
        self.c["transferts"] += transfert
        self.c["bloques_par_garde_fou"] += bloque
        self.c["tokens_entree"] += report.get("tokens_entree", 0)
        self.c["tokens_sortie"] += report.get("tokens_sortie", 0)
        self.latences.append(report.get("latence_s", 0))

    def summary(self) -> dict:
        """Les compteurs, la latence moyenne et les taux de transfert et de résolution sans humain."""
        tours = self.c["tours"] or 1
        return {**self.c, "latence_moyenne_s": round(sum(self.latences) / max(len(self.latences), 1), 2),
                "taux_transfert": round(self.c["transferts"] / tours, 3),
                "taux_resolution_sans_humain": round(1 - self.c["transferts"] / tours, 3)}
