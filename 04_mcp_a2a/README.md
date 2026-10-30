# Module 4 : Interopérabilité avec MCP et A2A

Ce module expose les prêts et les échéances de Lagune Banque dans un serveur MCP, puis connecte l'agent du module 3 à ce serveur. Il présente aussi l'injection indirecte par la description d'un outil tiers et le format Agent Card d'A2A.

Les démos sont présentées par le formateur ; le TP est à compléter (`# TODO`).

| Ordre | Dossier | Notion travaillée |
|---|---|---|
| 1 | `tp1_mcp_prets/` | Implémenter un serveur en lecture seule, le tester en stdio et en HTTP, puis connecter l'agent à ses outils |

## Code partagé

| Fichier | Rôle |
|---|---|
| `socle/outils.py` | Outils utilisés par l'agent du module 3 ; les données sont dans `data/` |
| `socle/pont_mcp.py` | Adaptation des outils MCP au format d'outils LangChain |

## Lancer

```bash
uv sync
uv run jupyter lab
```

Renseignez `LLM_API_KEY`, `MODELE` et `MODELE_EMBEDDING` dans `.env`. L'agent utilise le modèle de chat, et la recherche dans la documentation (`search_docs`) utilise le modèle d'embedding.
