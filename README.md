# GenAI Training

Formation « Agents IA & AI Engineering » : du prompt à un assistant déployé sur un canal de messagerie.
Le fil rouge est un assistant support client pour Lagune Banque (données fictives).

## Programme

Chaque module a un README qui liste ses notebooks dans l'ordre de passage, avec ce que chacun ajoute et mesure.

| Jour | Module | Contenu | Notebooks |
|---|---|---|---|
| Lun 02/11 | [1. Fondamentaux et prompting](01_fondamentaux_prompting/README.md) | paramètres de génération, réponses avec sources, prompting, sorties structurées, appels d'outils | 3 TP |
| Mar 03/11 | [2. RAG et données métier](02_rag/README.md) | découpage, reformulation, recherche hybride et reranking, réponses contrôlées, évaluation et interface | 4 TP |
| Mer 04/11 et jeu 05/11 (matin) | [3. Agents LangChain et LangGraph](03_agents/README.md) | outils, mémoire, sécurité, orchestration, traces et débogage | 5 TP |
| Jeu 05/11 (après-midi) | [4. Interopérabilité MCP et A2A](04_mcp_a2a/README.md) | serveur MCP, injection indirecte, connexion à un agent et Agent Card A2A | 1 TP |
| Ven 06/11 | [5. Canaux et gouvernance](05_canaux_gouvernance/README.md) | canal WhatsApp, garde-fous, validation humaine, suivi et coûts | 3 TP |

## Démarrer

Prérequis, à installer avant le jour 1 : Python 3.11 ou plus, [`uv`](https://docs.astral.sh/uv/), [Docker](https://docs.docker.com/get-docker/) (la base vectorielle Weaviate tourne en local dans un conteneur, dès le module 2) et une clé d'API de modèle.

```bash
uv sync
uv run jupyter lab
```

L'installation détaillée, le fichier `.env` et la liste des variables sont dans [`INSTALLATION.md`](INSTALLATION.md).

## Structure du dépôt

Le projet `uv` est à la racine : un seul `pyproject.toml`, un seul `.env`.

- `01_fondamentaux_prompting/` à `05_canaux_gouvernance/` : un dossier par module, avec ses TP et son socle.
- [`data/`](data/) : la base `banque.db`, le corpus `corpus/` et les jeux d'évaluation `evaluation/`.
- [`code_partage/`](code_partage/) : le code utilisé par plusieurs modules (`rag.py`, `rag_avance.py`, `weaviate_store.py`, `recherche_docs.py`, `observabilite.py`, `front.py`, `config.py`).
- [`scripts/`](scripts/) : `check_env.py` et `verifier_langfuse.py`.

## Données

`data/` est la source unique des données :

- `banque.db` : la base SQLite (clients, prêts, échéances, transactions).
- `corpus/` : dix documents (PDF, HTML, Word) décrits par `manifest.json`, avec version et dates de validité.
- `evaluation/` : les questions du module 2.

Les modules ne copient pas ces fichiers : leur code remonte l'arborescence jusqu'à `data/`. Les jeux propres à un seul TP (par exemple les messages du TP1 du module 1) restent dans le dossier du TP.

Le module 2 charge, découpe et indexe le corpus avec `code_partage/rag.py`. Les modules 3, 4 et 5 réutilisent cet index pour le tool `search_docs` : ils demandent donc aussi `MODELE_EMBEDDING`.

## Travail dans le dépôt

`main` est la branche de travail.
