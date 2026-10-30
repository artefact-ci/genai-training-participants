# Module 2 : RAG et données métier

Ce module construit un assistant qui répond à partir de la documentation de Lagune Banque (données fictives).
Chaque notebook ajoute une capacité au même assistant, et mesure ce qu'elle apporte. Les démos sont menées par le formateur, les TP sont à compléter (`# TODO`). À la fin, tout s'assemble dans une interface Gradio.

| Ordre | Notebook | Capacité ajoutée | Mesure |
|---|---|---|---|
| 1 | `tp1_chunking/` | Implémenter un splitter, mesurer des distances d'embeddings et comparer six index | présence d'une réponse complète dans un chunk |
| 2 | `tp2_hybrid_reranking/` | Combiner BM25 et recherche vectorielle avec RRF, puis reclasser les candidats | MRR sur un échantillon de 15 questions |
| 3 | `tp3_rag_sources/` | Implémenter un seuil de refus et vérifier les extraits cités dans les chunks | réponses métier, refus et citations vérifiées |
| 4 | `tp4_evaluation/` | Implémenter deux métriques et comparer trois versions du RAG avec quatre métriques inspirées de RAGAS | fidélité, pertinence, précision et rappel du contexte |

## Le code partagé

Dans `code_partage/` (les modules 3, 4 et 5 l'utilisent aussi pour la recherche documentaire) :

| Fichier | Contenu |
|---|---|
| `rag.py` | chargement (PDF, HTML, Word, scan), nettoyage, chunking, embeddings, recherche avec filtre de date, reranking, prompt, génération |
| `rag_avance.py` | réécriture, multi-requête, HyDE, BM25, fusion RRF, mesure du MRR, réponse avec citations vérifiées, juge |
| `weaviate_store.py` | base vectorielle : Weaviate (cloud ou local), ou une base en mémoire si Weaviate est injoignable |
| `config.py` | charge `.env` et vérifie la connexion aux modèles |
| `front.py` | thème et blocs de l'interface Gradio |

Les questions de mesure sont dans `data/evaluation/questions_rag.json` : 12 cas courants et 35 cas difficiles (fautes, anglais, nombres exacts, suites de conversation).

Les données sont dans `data/` : `corpus/` (dix documents décrits par `manifest.json`) et `banque.db`.

## Lancer

```bash
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
