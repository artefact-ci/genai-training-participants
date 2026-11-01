"""Traces Langfuse Cloud et masquage des données personnelles avant tout envoi.

Clés dans `.env` : LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY et LANGFUSE_HOST (la région du projet, voir le README).
Vérification : `uv run python scripts/verifier_langfuse.py`. Sans clés, rien n'est envoyé et rien ne casse.
Une trace contient des questions de clients : elle est masquée (`mask`) avant l'envoi.
"""
import hashlib
import os
import re
from typing import Optional

HOTE_PAR_DEFAUT = "https://cloud.langfuse.com"
_client = None


def langfuse_enabled() -> bool:
    """Les deux clés sont renseignées."""
    return bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))


# ------------------------------------------------------------------ masquage
def mask(texte: str) -> str:
    """Masque les données personnelles avant l'appel au modèle, et avant tout envoi dans une trace."""
    # téléphones, cartes, comptes : au moins 10 chiffres (une date ou un montant n'en ont pas autant)
    texte = re.sub(r"(?<!\d)\+?\d[\d .-]{8,}\d(?!\d)",
                   lambda m: "[NUMÉRO]" if sum(c.isdigit() for c in m.group(0)) >= 10 else m.group(0), texte)
    texte = re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "[EMAIL]", texte)
    texte = re.sub(r"(?i)(code(?: de vérification| secret| pin)?\s*(?:est|:)?\s*)\d{4,8}", r"\1[CODE]", texte)
    return texte


def mask_data(data):
    """Applique mask() à toute structure. Langfuse l'appelle comme `mask(data=...)` : le paramètre doit s'appeler `data`."""
    if isinstance(data, str):
        return mask(data)
    if isinstance(data, dict):
        return {k: mask_data(v) for k, v in data.items()}
    if isinstance(data, (list, tuple)):
        return [mask_data(v) for v in data]
    return data


# ------------------------------------------------------------------ Langfuse
def langfuse_client():
    """Le client Langfuse (un seul), avec le masquage branché ; None si Langfuse n'est pas configuré."""
    global _client
    if not langfuse_enabled():
        return None
    if _client is None:
        os.environ.setdefault("LANGFUSE_HOST", HOTE_PAR_DEFAUT)
        from langfuse import Langfuse
        # on écarte les spans de FastMCP : ils arriveraient en traces séparées, en double de celles de LangChain
        from langfuse.span_filter import is_default_export_span
        _client = Langfuse(mask=mask_data, should_export_span=lambda span: is_default_export_span(span)
                           and (span.instrumentation_scope is None or span.instrumentation_scope.name != "fastmcp"))
    return _client


def pseudonym(valeur: str, prefixe: str = "") -> str:
    """Identifiant stable et non réversible : un numéro de téléphone ou un chat_id ne doit jamais arriver tel quel dans une trace."""
    return prefixe + hashlib.sha256(valeur.encode()).hexdigest()[:10]


def langfuse_callbacks(session_id: str = "", utilisateur: str = "", tags: Optional[list[str]] = None, nom: str = "") -> tuple[list, dict]:
    """(callbacks, metadata) à ajouter à la config d'un appel LangChain ou LangGraph : `config={"callbacks": cb, "metadata": meta}`.
    Les deux sont vides si Langfuse n'est pas configuré. Les traces d'une même conversation partagent `session_id`.
    `nom` : le nom de la trace dans Langfuse (convention `m<module>-<usage>`, en minuscules)."""
    if langfuse_client() is None:
        return [], {}
    from langfuse.langchain import CallbackHandler
    meta = {}
    if session_id:
        meta["langfuse_session_id"] = session_id
    if utilisateur:
        meta["langfuse_user_id"] = utilisateur
    if tags:
        meta["langfuse_tags"] = tags
    if nom:
        meta["langfuse_trace_name"] = nom
    return [CallbackHandler()], meta


def clear_langfuse() -> None:
    """À appeler en fin de notebook ou d'exécution : envoie les traces en attente (elles partent par lots, en tâche de fond)."""
    if _client is not None:
        _client.flush()
