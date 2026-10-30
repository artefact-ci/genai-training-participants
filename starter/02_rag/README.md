# Module 2 : RAG et données métier

Ce module construit un assistant qui répond à partir de la documentation de Lagune Banque (données fictives).
Chaque notebook ajoute une capacité au même assistant, et mesure ce qu'elle apporte. Les démos sont menées par le formateur, les TP sont à compléter (`# TODO`). À la fin, tout s'assemble dans une interface Gradio.

| Ordre | Notebook | Capacité ajoutée | Mesure |
|---|---|---|---|
| 1 | `demos/demo1_chunking/` | Visualiser le découpage fixe, récursif, par structure et sémantique, ainsi que le cas des tableaux | frontières et contenu des chunks |
| 2 | `tp1_chunking/` | Implémenter un splitter, mesurer des distances d'embeddings et comparer six index | présence d'une réponse complète dans un chunk |
| 3 | `demos/demo2_query_rewriting/` | Comparer la réécriture, la multi-requête avec fusion RRF et HyDE | MRR et coût par méthode |
| 4 | `tp2_hybrid_reranking/` | Combiner BM25 et recherche vectorielle avec RRF, puis reclasser les candidats | MRR sur un échantillon de 15 questions |
| 5 | `demos/demo3_grounding_check/` | Comparer la vérification des sources, des chiffres et des affirmations par un modèle juge | défauts détectés par chaque contrôle |
| 6 | `tp3_rag_sources/` | Implémenter un seuil de refus et vérifier les extraits cités dans les chunks | réponses métier, refus et citations vérifiées |
| 7 | `tp4_evaluation/` | Implémenter deux métriques et comparer trois versions du RAG avec quatre métriques inspirées de RAGAS | fidélité, pertinence, précision et rappel du contexte |
| 8 | `demos/demo4_gradio_assistant/` | Assembler les capacités dans une interface Gradio activable par options | effet et temps de chaque capacité |

## Le code partagé

Dans `starter/code_partage/` (les modules 3, 4 et 5 l'utilisent aussi pour la recherche documentaire) :

| Fichier | Contenu |
|---|---|
| `rag.py` | chargement (PDF, HTML, Word, scan), nettoyage, chunking, embeddings, recherche avec filtre de date, reranking, prompt, génération |
| `rag_avance.py` | réécriture, multi-requête, HyDE, BM25, fusion RRF, mesure du MRR, réponse avec citations vérifiées, juge |
| `weaviate_store.py` | base vectorielle : Weaviate (cloud ou local), ou une base en mémoire si Weaviate est injoignable |
| `config.py` | charge `.env` et vérifie la connexion aux modèles |
| `front.py` | thème et blocs de l'interface Gradio |

Les questions de mesure sont dans `starter/data/evaluation/questions_rag.json` : 12 cas courants et 35 cas difficiles (fautes, anglais, nombres exacts, suites de conversation).

Les données sont dans `starter/data/` : `corpus/` (dix documents décrits par `manifest.json`) et `banque.db`.

## Lancer

```bash
cd starter
uv sync
uv run jupyter lab
```

Renseignez dans `.env` : `LLM_API_KEY`, `MODELE` et `MODELE_EMBEDDING`. Le reranking (TP2 et suivants) demande aussi `MODELE_RERANK`, `RERANK_API_KEY` et, selon le fournisseur, `RERANK_API_BASE` : voir `.env.example`.

Pour utiliser Weaviate, lancez `docker compose up -d` à la racine du dépôt. Sinon, la base en mémoire prend le relais.

Le reranker est un service à débit limité, partagé par la salle : le TP2 se limite à 15 questions, le TP4 à une vingtaine.

## Particularités du corpus

- La note de service DOC-10 est un scan : on n'en extrait aucun texte. `note_service_incident.ocr.txt` en contient la transcription.
- Chaque page de PDF commence par le même en-tête. `rag.strip_headers` le supprime.
- La procédure de régularisation existe en deux versions : DOC-07 jusqu'au 30/06/2026, DOC-08 depuis le 01/07/2026.
  La date de la situation détermine la version applicable. Utilisez `rag.search(..., date=...)`.

## Origine

Ce module reprend et adapte le TP de chunking et le TP d'observabilité Langfuse de souleymanecoulibaly-stack
(branche `tp-rag-lagune-bank`, commit `8ba70e2`). Il utilise le corpus de Lagune Banque et LiteLLM.

## Pour aller plus loin

`bonus_langfuse/` : suivre les étapes du RAG dans Langfuse (traces détaillées, scores, jeux de données et expériences), puis comparer les exécutions. Facultatif : à lire après la démo de trace du module 3, où Langfuse est présenté. Les clés sont à configurer dans `.env` ; elles ne doivent jamais être inscrites dans le notebook.
