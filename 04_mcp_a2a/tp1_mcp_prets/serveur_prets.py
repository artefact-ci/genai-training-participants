"""Serveur MCP de Lagune Banque : prêts et échéances en lecture seule (TP1 du module 4).

Lancement : `python serveur_prets.py` (stdio, l'hôte fixe CLIENT_ID) ou `--http` (HTTP, en-tête X-Client-Id).
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(next(p / "socle" for p in Path(__file__).resolve().parents if (p / "socle" / "loans.py").exists())))

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_http_headers
from loans import _get_customer_loans, _get_schedule, _search_docs  # noqa: F401

mcp = FastMCP("lagune-prets")


def client_courant() -> str:
    """Le client identifié par l'HÔTE, jamais choisi par le modèle : en-tête HTTP, ou variable d'environnement (stdio)."""
    client_id = get_http_headers().get("x-client-id") or os.environ.get("CLIENT_ID")
    if not client_id:
        raise ToolError("Client non identifié : l'hôte doit fournir CLIENT_ID (stdio) ou l'en-tête X-Client-Id (HTTP).")
    return client_id


# TODO 1 : exposez get_customer_loans comme outil MCP, en lecture seule.
# Décorateur : @mcp.tool(annotations={"readOnlyHint": True}). Le modèle lit la docstring : décrivez bien l'outil.
# Le client est celui de l'hôte : client_courant(), jamais un paramètre que le modèle remplirait.
def get_customer_loans() -> dict:
    """TODO : décrivez l'outil pour le modèle."""
    raise NotImplementedError("TODO 1")


# TODO 2 : même chose pour get_schedule, avec un paramètre optionnel pret_id (str | None).
def get_schedule(pret_id: str | None = None) -> dict:
    """TODO : décrivez l'outil pour le modèle."""
    raise NotImplementedError("TODO 2")


# BONUS (après le TP) : ajoutez une resource lagune://procedures/regularisation (@mcp.resource) qui renvoie la
# procédure en vigueur (_search_docs), et un prompt diagnostic_remboursement(date_remboursement) (@mcp.prompt).


if __name__ == "__main__":
    if "--http" in sys.argv:
        mcp.run(transport="http", host="127.0.0.1", port=8765)
    else:
        mcp.run(show_banner=False)
