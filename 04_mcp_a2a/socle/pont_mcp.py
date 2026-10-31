"""Pont MCP -> LangChain : fait des outils d'un serveur MCP des outils utilisables par un agent LangGraph.

Un hôte MCP fait exactement ceci : il se connecte au serveur, liste ses outils (nom, description, schéma JSON),
puis transmet au serveur chaque appel décidé par le modèle.
"""
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Optional

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from langchain_core.tools import StructuredTool


def stdio_transport(script, env: Optional[dict] = None) -> StdioTransport:
    """Transport stdio vers un script serveur. `env` : variables fixées par l'HÔTE (ex. {"CLIENT_ID": "CLI-0002"}).
    La sortie d'erreur du serveur va dans un fichier : un notebook n'a pas de vraie sortie d'erreur à lui donner."""
    journal = Path(tempfile.gettempdir()) / "serveur_mcp_stderr.log"
    # le serveur cherche dans la documentation (embeddings) : il lui faut le modèle, la clé et la base vectorielle
    heritees = {v: os.environ[v] for v in ("LLM_API_KEY", "MODELE_EMBEDDING", "VECTEUR", "WEAVIATE_URL", "WEAVIATE_API_KEY") if v in os.environ}
    return StdioTransport(sys.executable, [str(script)], env={**heritees, **(env or {})}, log_file=journal)


class MCPConnection:
    """Connexion à un serveur MCP, à ouvrir avec `async with`. `transport` : chemin d'un script (stdio),
    URL (HTTP) ou transport fastmcp (StdioTransport, StreamableHttpTransport) quand il faut des variables
    d'environnement ou des en-têtes."""

    def __init__(self, transport):
        self.client = Client(transport)

    async def __aenter__(self):
        await self.client.__aenter__()
        return self

    async def __aexit__(self, *exc):
        await self.client.__aexit__(*exc)

    async def definitions(self):
        """Les outils tels que le serveur les décrit : c'est ce que le modèle va lire (nom, description, schéma)."""
        return await self.client.list_tools()

    async def tools(self, allowed: Optional[set[str]] = None) -> list[StructuredTool]:
        """Les outils du serveur, en outils LangChain. `allowed` : liste blanche de noms (None = tous)."""
        resultat = []
        for d in await self.definitions():
            if allowed is not None and d.name not in allowed:
                continue
            resultat.append(StructuredTool.from_function(
                coroutine=self._call_tool(d.name), name=d.name, description=d.description or "",
                args_schema=d.inputSchema))
        return resultat

    def _call_tool(self, nom: str):
        """La fonction qui transmet l'appel au serveur ; une erreur revient au modèle sous forme de texte."""
        async def appel(**arguments) -> str:
            r = await self.client.call_tool(nom, arguments, raise_on_error=False)
            if r.is_error:
                return json.dumps({"erreur": " ".join(getattr(c, "text", "") for c in r.content)}, ensure_ascii=False)
            return json.dumps(r.data, ensure_ascii=False, default=str) if r.data is not None else \
                " ".join(getattr(c, "text", "") for c in r.content)
        return appel
