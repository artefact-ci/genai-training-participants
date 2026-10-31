# GenAI Training

Formation AI Engineering.
Le fil rouge est un assistant support client pour Lagune Banque (données fictives).

## Programme

| Jour | Module | Contenu |
|---|---|---|
| Lun 02/11 | [1. Fondamentaux et prompting](01_fondamentaux_prompting/README.md) | paramètres de génération, réponses avec sources, prompting, sorties structurées, appels d'outils |
| Mar 03/11 | [2. RAG et données métier](02_rag/README.md) | découpage, reformulation, recherche hybride et reranking, réponses contrôlées, évaluation et interface |
| Mer 04/11 et jeu 05/11 (matin) | [3. Agents LangChain et LangGraph](03_agents/README.md) | outils, mémoire, sécurité, orchestration, traces et débogage |
| Jeu 05/11 (après-midi) | [4. Interopérabilité MCP et A2A](04_mcp_a2a/README.md) | serveur MCP, injection indirecte, connexion à un agent et Agent Card A2A |
| Ven 06/11 | [5. Canaux et gouvernance](05_canaux_gouvernance/README.md) | canal WhatsApp, garde-fous, validation humaine, suivi et coûts |

## Démarrer

Prérequis : [`uv`](https://docs.astral.sh/uv/getting-started/installation/), Git, et [Docker](https://docs.docker.com/get-docker/).

```bash
git clone <url> && cd <dossier du dépôt>
cp .env.example .env          # renseignez vos clés
uv sync
uv run scripts/check_env.py   # doit afficher OK
uv run jupyter lab
```

Variables de `.env` :

- `LLM_API_KEY` et `MODELE` : obligatoires.
- `MODELE_EMBEDDING` : embeddings.
- `MODELE_RERANK`, `RERANK_API_KEY`, `RERANK_API_BASE` : reranker.

### Langfuse (facultatif)

1. Créer un compte Hobby sur <https://cloud.langfuse.com> (gratuit), puis un projet.
2. *Settings > API Keys* : copier `LANGFUSE_PUBLIC_KEY` et `LANGFUSE_SECRET_KEY` dans `.env`.
3. Régler `LANGFUSE_HOST` sur la région du projet : `https://cloud.langfuse.com` (Europe, défaut) ou `https://us.cloud.langfuse.com`.
4. `uv run scripts/verifier_langfuse.py` doit afficher `OK`.

## Structure du dépôt

- `01_fondamentaux_prompting/` à `05_canaux_gouvernance/` : un dossier par module, avec ses TP et son socle.
- [`data/`](data/) : la base `banque.db`, le corpus `corpus/` et les jeux d'évaluation `evaluation/`.
- [`code_partage/`](code_partage/) : le code utilisé par plusieurs modules (`rag.py`, `rag_advanced.py`, `weaviate_store.py`, `doc_search.py`, `observability.py`, `front.py`, `config.py`).
- [`scripts/`](scripts/) : `check_env.py` et `verifier_langfuse.py`.
