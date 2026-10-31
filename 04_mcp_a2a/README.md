# Module 4 : Interopérabilité avec MCP et A2A

| Dossier | Description |
|---|---|
| `tp1_mcp_prets/` | Implémenter un serveur en lecture seule, le tester en stdio et en HTTP, puis y connecter l'agent |

## Le socle

| Fichier | Contenu |
|---|---|
| `socle/loans.py` | accès aux prêts et à la documentation, utilisé par le serveur MCP |
| `socle/mcp_bridge.py` | adaptation des outils MCP au format LangChain |

## Prérequis

- `.env` : `LLM_API_KEY`, `MODELE` et `MODELE_EMBEDDING` (pour `search_docs`).
