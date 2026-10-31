"""Accès aux données de Lagune Banque, repris du TP1 du module 3 : prêts, échéances, documentation.

Les serveurs MCP du module exposent ces fonctions `_xxx` comme outils. S'y ajoutent le modèle (`new_model`) et
l'affichage d'un tour d'agent (`print_trace`).
"""
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

DATA = next(p / "data" for p in Path(__file__).resolve().parents if (p / "data" / "banque.db").exists())   # le dossier data/ du dépôt
sys.path.insert(0, str(next(p / "code_partage" for p in Path(__file__).resolve().parents if (p / "code_partage" / "doc_search.py").exists())))
from doc_search import find_docs  # noqa: E402  (recherche dans la documentation, code_partage/)

AUJOURDHUI = "2026-11-16"                                         # date de référence des données
BASE = str(Path(tempfile.gettempdir()) / "lagune_banque_tp.db")   # copie de travail de data/banque.db


def reset_db():
    """Remet la copie de travail dans l'état d'origine (utile entre deux essais qui la modifient)."""
    shutil.copy(DATA / "banque.db", BASE)


reset_db()   # chaque import repart de la base d'origine


def connect():
    """Connexion à la copie de travail ; les colonnes se lisent par leur nom."""
    con = sqlite3.connect(BASE)
    con.row_factory = sqlite3.Row
    return con


def _get_customer_loans(client_id):
    """Prêts du client, du plus ancien au plus récent."""
    with connect() as con:
        return {"prets": [dict(r) for r in con.execute(
            "SELECT pret_id, produit, montant, frais_service, date_octroi, duree_jours, statut, solde_restant, suspension "
            "FROM prets WHERE client_id = ? ORDER BY date_octroi", (client_id,))]}


def _get_schedule(client_id, pret_id=None):
    """Échéanciers des prêts en cours ou impayés du client (un seul prêt si `pret_id` est donné)."""
    with connect() as con:
        prets = con.execute("SELECT * FROM prets WHERE client_id = ? AND statut IN ('en_cours', 'impaye') "
                            "AND (? IS NULL OR pret_id = ?)", (client_id, pret_id, pret_id)).fetchall()
        if not prets:
            return {"erreur": "Aucun prêt en cours pour ce client."}
        return {"date_du_jour": AUJOURDHUI, "prets": [
            {"pret_id": p["pret_id"], "produit": p["produit"], "solde_restant": p["solde_restant"],
             "suspension": bool(p["suspension"]),
             "echeances": [dict(e) for e in con.execute(
                 "SELECT echeance_id, pret_id, numero, date_echeance, montant_du, montant_paye, statut, frais_retard "
                 "FROM echeances WHERE pret_id = ? ORDER BY numero", (p["pret_id"],))]} for p in prets]}


def _search_docs(requete, date_reference=None, k=3):
    """Recherche dans l'index RAG du module 2, limitée aux documents en vigueur à date_reference."""
    date_reference = date_reference or AUJOURDHUI
    return {"date_reference": date_reference, "resultats": find_docs(requete, date_reference, k)}


from langchain_core.messages import AIMessage, HumanMessage, ToolMessage


def new_model():
    """Le modèle défini dans .env (MODELE, LLM_API_KEY), via LiteLLM, à température 0."""
    from langchain_litellm import ChatLiteLLM
    return ChatLiteLLM(model=os.getenv("MODELE"), api_key=os.getenv("LLM_API_KEY"), temperature=0)


def print_trace(resultat):
    """Affiche les appels d'outils et la réponse du dernier tour."""
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


# Le cas fil rouge : un remboursement réussi mais non rattaché à son échéance.
KOUASSI = "J'ai remboursé mon prêt hier via Lagune Money, mais mon dossier indique toujours un impayé."
