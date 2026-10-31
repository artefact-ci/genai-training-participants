# Module 2 : RAG et données métier

| Ordre | Notebook | Capacité ajoutée | Mesure |
|---|---|---|---|
| 1 | `tp1_chunking/` | Implémenter un splitter, mesurer des distances d'embeddings et comparer six index | présence d'une réponse complète dans un chunk |
| 2 | `tp2_hybrid_reranking/` | Combiner BM25 et recherche vectorielle avec RRF, puis reclasser les candidats | MRR sur un échantillon de 15 questions |
| 3 | `tp3_rag_sources/` | Implémenter un seuil de refus et vérifier les extraits cités dans les chunks | réponses métier, refus et citations vérifiées |
| 4 | `tp4_evaluation/` | Implémenter deux métriques et comparer trois versions du RAG avec quatre métriques inspirées de RAGAS | fidélité, pertinence, précision et rappel du contexte |

## Le code partagé

`code_partage/`, aussi utilisé par les modules 3 à 5 pour la recherche documentaire :

| Fichier | Contenu |
|---|---|
| `rag.py` | chargement (PDF, HTML, Word, scan), nettoyage, chunking, embeddings, recherche avec filtre de date, reranking, prompt, génération |
| `rag_advanced.py` | réécriture, multi-requête, HyDE, BM25, fusion RRF, mesure du MRR, réponse avec citations vérifiées, juge |
| `weaviate_store.py` | base vectorielle : Weaviate (cloud ou local), ou une base en mémoire si Weaviate est injoignable |
| `config.py` | charge `.env` et vérifie la connexion aux modèles |
| `front.py` | thème et blocs de l'interface Gradio |

Les questions de mesure sont dans `data/evaluation/questions_rag.json` : 12 cas courants et 35 cas difficiles (fautes, anglais, nombres exacts, suites de conversation).

## Prérequis

- `.env` : `LLM_API_KEY`, `MODELE`, `MODELE_EMBEDDING`, et pour le reranking (TP2 et suivants) `MODELE_RERANK`, `RERANK_API_KEY`, `RERANK_API_BASE` (voir `.env.example`).
- Weaviate : `docker compose up -d` à la racine du dépôt. Sans Docker, une base en mémoire prend le relais.
- Le reranker est partagé par la salle et limité en débit : 15 questions au TP2, une vingtaine au TP4.

## Particularités du corpus

- La note de service DOC-10 est un scan : on n'en extrait aucun texte. `note_service_incident.ocr.txt` en contient la transcription.
- Chaque page de PDF commence par le même en-tête. `rag.strip_headers` le supprime.
- La procédure de régularisation existe en deux versions : DOC-07 jusqu'au 30/06/2026, DOC-08 depuis le 01/07/2026.
  La date de la situation détermine la version applicable. Utilisez `rag.search(..., date=...)`.

## Origine

TP de chunking et TP d'observabilité Langfuse adaptés de souleymanecoulibaly-stack (branche `tp-rag-lagune-bank`, commit `8ba70e2`).
