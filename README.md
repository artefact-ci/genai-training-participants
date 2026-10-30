# GenAI Training

Formation « Agents IA & AI Engineering » : du prompt à un assistant déployé sur un canal de messagerie.
Le fil rouge est un assistant support client pour Lagune Banque (données fictives).

## Programme

Chaque module a un README qui liste ses notebooks dans l'ordre de passage, avec ce que chacun ajoute et mesure.

| Jour | Module | Contenu | Notebooks |
|---|---|---|---|
| Lun 02/11 | [1. Fondamentaux et prompting](starter/01_fondamentaux_prompting/README.md) ([dossier](starter/01_fondamentaux_prompting/)) | tokens, paramètres de génération, réponses avec sources, prompting, sorties structurées, appels d'outils | 6 démos, 3 TP |
| Mar 03/11 | [2. RAG et données métier](starter/02_rag/README.md) ([dossier](starter/02_rag/)) | découpage, reformulation, recherche hybride et reranking, réponses contrôlées, évaluation et interface | 4 démos, 4 TP, 1 bonus |
| Mer 04/11 et jeu 05/11 (matin) | [3. Agents LangChain et LangGraph](starter/03_agents/README.md) ([dossier](starter/03_agents/)) | outils, mémoire, sécurité, orchestration, traces et débogage | 4 démos, 5 TP, 1 bonus |
| Jeu 05/11 (après-midi) | [4. Interopérabilité MCP et A2A](starter/04_mcp_a2a/README.md) ([dossier](starter/04_mcp_a2a/)) | serveur MCP, injection indirecte, connexion à un agent et Agent Card A2A | 4 démos, 1 TP |
| Ven 06/11 | [5. Canaux et gouvernance](starter/05_canaux_gouvernance/README.md) ([dossier](starter/05_canaux_gouvernance/)) | canal WhatsApp, garde-fous, validation humaine, suivi et coûts | 3 démos, 3 TP |

## Démarrer

Prérequis, à installer avant le jour 1 : Python 3.11 ou plus, [`uv`](https://docs.astral.sh/uv/), [Docker](https://docs.docker.com/get-docker/) (la base vectorielle Weaviate tourne en local dans un conteneur, dès le module 2) et une clé d'API de modèle.

```bash
cd starter
uv sync
uv run jupyter lab
```

L'installation détaillée, le fichier `.env` et la liste des variables sont dans [`starter/README.md`](starter/README.md).

## Structure du dépôt

| Dossier | Contenu | Public |
|---|---|---|
| [`starter/`](starter/) | projet `uv` : un dossier par module (TP, démos, code de départ), données, code partagé | participants (sparse checkout) |
| [`solutions/`](solutions/) | solutions des TP, par module, et script de vérification | formateur |

Dans `starter/` :

- `01_fondamentaux_prompting/` à `05_canaux_gouvernance/` : un dossier par module.
- [`data/`](starter/data/) : la base `banque.db`, le corpus `corpus/` et les jeux d'évaluation `evaluation/` (avec les résultats de référence mesurés par le formateur).
- [`code_partage/`](starter/code_partage/) : le code utilisé par plusieurs modules (`rag.py`, `rag_avance.py`, `weaviate_store.py`, `recherche_docs.py`, `observabilite.py`, `front.py`, `config.py`).
- [`scripts/`](starter/scripts/) : `check_env.py` et `verifier_langfuse.py`.

## Données

`starter/data/` est la source unique des données :

- `banque.db` : la base SQLite (clients, prêts, échéances, transactions).
- `corpus/` : dix documents (PDF, HTML, Word) décrits par `manifest.json`, avec version et dates de validité.
- `evaluation/` : les questions du module 2 et les résultats de référence ([module 2](starter/data/evaluation/resultats_de_reference.md), [module 3](starter/data/evaluation/resultats_de_reference_agents.md)).

Les modules ne copient pas ces fichiers : leur code remonte l'arborescence jusqu'à `starter/data/`. Les jeux propres à un seul TP (par exemple les messages du TP1 du module 1) restent dans le dossier du TP.

Le module 2 charge, découpe et indexe le corpus avec `code_partage/rag.py`. Les modules 3, 4 et 5 réutilisent cet index pour le tool `search_docs` : ils demandent donc aussi `MODELE_EMBEDDING`.

## Travail dans le dépôt

`main` est la branche de travail.
