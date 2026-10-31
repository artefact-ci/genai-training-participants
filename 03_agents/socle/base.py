"""Socle du module 3 : base de travail, contexte d'exécution, modèle et affichage des conversations, partagés par les TP."""
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data" / "banque.db").exists())
DATA = ROOT / "data"
sys.path.insert(0, str(ROOT / "code_partage"))  # doc_search, front, observability

AUJOURDHUI = "2026-11-16"  # date de référence des données fictives
HIER = "2026-11-15"
# Copie de travail de banque.db, propre à chaque processus : la base d'origine n'est jamais modifiée.
BASE = str(Path(tempfile.gettempdir()) / f"lagune_banque_tp_{os.getpid()}.db")
# Message de M. Kouassi (CLI-0002), le cas fil rouge du module.
KOUASSI = "J'ai remboursé mon prêt hier via Lagune Money, mais mon dossier indique toujours un impayé."


@dataclass
class Context:
    """Contexte d'exécution rempli par l'application, invisible pour le modèle. `validateur` : identifiant du
    conseiller qui autorise une régularisation (None tant que personne n'a validé)."""
    client_id: str
    validateur: Optional[str] = None


def reset_db():
    """Remet la copie de travail dans l'état de banque.db."""
    shutil.copy(DATA / "banque.db", BASE)


def sql(requete, params=()):
    """Exécute une requête SELECT sur la copie de travail et renvoie un DataFrame."""
    with sqlite3.connect(BASE) as con:
        return pd.read_sql_query(requete, con, params=params)


def connect():
    """Connexion à la copie de travail ; les lignes se lisent comme des dictionnaires."""
    con = sqlite3.connect(BASE)
    con.row_factory = sqlite3.Row
    return con


def new_model():
    """Modèle configuré dans .env (MODELE, LLM_API_KEY), appelé via LiteLLM, température 0."""
    from langchain_litellm import ChatLiteLLM
    return ChatLiteLLM(model=os.getenv("MODELE"), api_key=os.getenv("LLM_API_KEY"), temperature=0)


def print_trace(resultat):
    """Affiche le dernier tour d'un résultat d'agent : message du client, appels de tools, résultats et réponse."""
    msgs = resultat["messages"]
    debut = max(i for i, m in enumerate(msgs) if isinstance(m, HumanMessage))
    for m in msgs[debut:]:
        if isinstance(m, HumanMessage):
            print(f"CLIENT    : {m.content}")
        elif isinstance(m, AIMessage) and m.tool_calls:
            for tc in m.tool_calls:
                print(f"  → {tc['name']}({json.dumps(tc['args'], ensure_ascii=False)[:150]})")
        elif isinstance(m, ToolMessage):
            print(f"  ← {m.name} : {str(m.content)[:160]}")
        elif isinstance(m, AIMessage):
            print(f"ASSISTANT : {m.content}")
    if resultat.get("__interrupt__"):
        print("⏸  EN ATTENTE DE VALIDATION HUMAINE")


def tools_called(resultat):
    """Noms des tools appelés pendant le dernier tour, dans l'ordre."""
    msgs = resultat["messages"]
    debut = max(i for i, m in enumerate(msgs) if isinstance(m, HumanMessage))
    return [tc["name"] for m in msgs[debut:] if isinstance(m, AIMessage) for tc in m.tool_calls]


def model_calls(resultat):
    """Nombre d'appels au modèle pendant le dernier tour."""
    msgs = resultat["messages"]
    debut = max(i for i, m in enumerate(msgs) if isinstance(m, HumanMessage))
    return sum(isinstance(m, AIMessage) for m in msgs[debut:])
