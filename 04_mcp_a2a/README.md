# Module 4 : Interopérabilité avec MCP et A2A

Serveur MCP des prêts et des échéances de Lagune Banque, connecté à l'agent du module 3.

| Ordre | Dossier | Notion travaillée |
|---|---|---|
| 1 | `tp1_mcp_prets/` | Implémenter un serveur en lecture seule, le tester en stdio et en HTTP, puis connecter l'agent à ses outils |

## Socle

| Fichier | Rôle |
|---|---|
| `socle/outils.py` | Accès aux données des prêts et à la documentation, utilisé par le serveur MCP ; les données sont dans `data/` |
| `socle/pont_mcp.py` | Adaptation des outils MCP au format d'outils LangChain |

## Prérequis

`.env` : `LLM_API_KEY`, `MODELE` (agent) et `MODELE_EMBEDDING` (`search_docs`).
