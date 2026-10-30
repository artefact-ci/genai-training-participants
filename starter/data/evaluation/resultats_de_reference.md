# Résultats de référence du module 2

Mesures réalisées le 27/10/2026 pendant la préparation du module, pour que le formateur sache à quoi s'attendre. Les techniques qui appellent le modèle de langage donnent des résultats qui varient légèrement d'une exécution à l'autre : comptez environ 0,03 de MRR.

## Conditions

| Élément | Valeur |
|---|---|
| Modèle de chat | `gemini/gemini-3.5-flash-lite` |
| Modèle d'embedding | `gemini/gemini-embedding-2` (vecteurs de 3 072 dimensions) |
| Reranker | `azure_ai/Cohere-rerank-v4.0-fast`, Azure AI Foundry, région eastus |
| Base vectorielle | Weaviate 1.40.0 en local (Docker), distance `l2-squared` |
| Découpage de référence | récursif, 500 caractères, recouvrement 75 (106 chunks) |
| Date de référence des questions | 2026-11-16 |
| Questions | `questions_rag.json` : 12 cas courants, 35 cas difficiles (20 écrits, 15 générés puis filtrés par un modèle critique) |

Le **MRR** est la moyenne de `1 / rang`, où le rang est la position du premier chunk qui contient tous les éléments de la réponse. 1,00 est le maximum.

## TP1 : six configurations de découpage

Réponses complètes dans un même chunk, parmi les 3 premiers, sur 7 questions.

| Configuration | Chunks | Longueur moyenne | Finissent par une fin de phrase | Réponses complètes |
|---|---|---|---|---|
| fixe, 200 caractères | 253 | 193 | 9 % | 4 / 7 |
| récursif, 200 | 278 | 153 | 65 % | 6 / 7 |
| fixe, 500 | 104 | 464 | 15 % | 7 / 7 |
| récursif, 500 | 106 | 417 | 58 % | 7 / 7 |
| fixe, 1000 | 57 | 836 | 26 % | 7 / 7 |
| récursif, 1000 | 58 | 795 | 67 % | 7 / 7 |

Distances entre embeddings (`l2-squared`) : question et chunk pertinent 0,41 ; question et chunk hors sujet 0,86 ; paraphrase et chunk pertinent 0,54 ; paraphrase et chunk hors sujet 0,77.

## Démo 2 : reformuler la question

MRR, 47 questions.

| Technique | Cas courants (12) | Cas difficiles (35) | Suites de conversation (4) | Échecs du départ (15) | Secondes par question | Appels au modèle |
|---|---|---|---|---|---|---|
| Vectoriel seul | 0,80 | 0,62 | 0,69 | 0,30 | 0,7 | 0 |
| Réécriture fidèle | 0,80 | 0,67 | 1,00 | 0,30 | 1,5 | 1 |
| Réécriture avec mots-clés | 0,69 | 0,61 | 1,00 | 0,42 | 1,6 | 1 |
| Multi-requête (RRF) | 0,80 | 0,63 | 0,71 | 0,37 | 4,0 | 1 |
| HyDE | 0,78 | 0,60 | 0,60 | 0,38 | 1,9 | 1 |

MRR par famille de cas difficiles, vectoriel seul, réécriture avec mots-clés, réécriture fidèle (première mesure) : anglais 1,00 / 0,67 / 1,00, bruitées 0,88 / 0,67 / 0,88, courtes 0,88 / 0,81 / 0,88, nombres exacts 0,88 / 0,75 / 0,88, suites de conversation 0,69 / 1,00 / 1,00, échecs du départ 0,30 / 0,46 / 0,30.

Une première version de la réécriture, qui ajoutait des synonymes et des mots-clés à toutes les questions, donnait 0,62 sur les cas courants (contre 0,80 pour le vectoriel) : elle déformait les questions déjà claires.

## Reranker sur l'ensemble des questions

Mesure complète faite avant l'ajout des nouvelles tentatives automatiques. Les chiffres du reranker sur les cas difficiles sont **incomplets** : certains appels ont échoué sur la limite de débit.

| Configuration | Cas courants (12), MRR | Bon chunk en 1er | Cas difficiles (35), MRR |
|---|---|---|---|
| Vectoriel seul | 0,80 | 8 / 12 | 0,62 |
| BM25 seul | 0,78 | 8 / 12 | 0,50 |
| Hybride (RRF) | 0,76 | 8 / 12 | 0,59 |
| Vectoriel top-20, puis reranker | **0,92** | 10 / 12 | 0,70 (partiel) |
| Hybride, puis reranker | 0,92 | 10 / 12 | non mesuré |

Sur un premier jeu de 10 questions difficiles (sans les questions générées), le reranker donnait un MRR de 1,00 (10 / 10 en première position), contre 0,85 pour le vectoriel seul, pour 0,4 seconde de plus par question.

## TP2 : échantillon de 15 questions

6 cas courants et 9 cas difficiles. Un écart inférieur à 0,1 n'est pas significatif.

| Configuration | MRR | En 1er | Cas courants | Cas difficiles | Secondes par question |
|---|---|---|---|---|---|
| Vectoriel | 0,65 | 6 / 15 | 0,81 | 0,54 | 0,7 |
| BM25 | 0,66 | 8 / 15 | 0,65 | 0,67 | 0,0 |
| Hybride | 0,70 | 9 / 15 | 0,78 | 0,65 | 0,8 |
| Vectoriel + reranker | 0,79 | 10 / 15 | 0,83 | 0,76 | 1,2 |
| Hybride + reranker | 0,78 | 10 / 15 | 0,83 | 0,74 | 1,2 |

## Limite de débit du reranker

Le déploiement `Cohere-rerank-v4.0-fast` refuse les appels au-delà de 23 appels environ en 14 secondes (message `RateLimitReached`). Avec les nouvelles tentatives de `rag.rerank`, 60 appels d'affilée aboutissent tous, en 123 secondes. Le TP2 se limite à 15 questions (30 appels) par élève. Avant la formation, vérifier le quota du déploiement dans Azure AI Foundry.

## Mesure complète : le pipeline, une technique ajoutée à la fois

MRR sur les 47 questions (12 courantes, 35 difficiles), mesure faite avec les nouvelles tentatives du reranker, donc complète.

| Étape | Courants (12) | Difficiles (35) | Secondes par question | Appels au modèle |
|---|---|---|---|---|
| 1. Départ : vectoriel seul | 0,80 | 0,62 | 0,8 | 0 |
| 2. + réécriture fidèle | 0,80 | 0,64 | 1,6 | 1 |
| 3. + recherche hybride (BM25) | 0,78 | 0,59 | 1,5 | 1 |
| 4. Vectoriel + reranker | 0,92 | 0,73 | 2,0 | 0 |
| 5. Réécriture + hybride + reranker | 0,92 | 0,76 | 3,6 | 1 |
| 6. Réécriture + vectoriel + reranker | 0,92 | 0,75 | 3,1 | 1 |

Lecture : le reranker est la seule technique qui change nettement le résultat (+0,12 sur les cas courants, +0,11 sur les difficiles). La réécriture et l'hybride, seuls, restent dans la marge d'erreur (0,03) ; l'hybride dégrade même légèrement. Combinés au reranker, ils ajoutent au mieux +0,03 pour une seconde et demie de plus par question : à ne retenir que si le cas d'usage le justifie.

## TP3 : signal de refus hors corpus

Score du reranker du meilleur chunk, 8 questions du corpus et 8 hors corpus : 0,88 à 0,93 contre 0,10 à 0,76. La distance vectorielle ne sépare pas les deux groupes (0,46 à 0,65 contre 0,52 à 0,97). Question la plus proche de la limite : « Pouvez-vous m'accorder un prêt de 200 000 FCFA dès aujourd'hui ? » (0,76).

## TP4 : les trois versions de l'assistant, sur 13 questions métier et 3 pièges

6 cas courants et 7 cas difficiles sans suite de conversation, plus 3 pièges hors corpus. Deux exécutions complètes ont donné :

| Version | Exactitude | Rappel du contexte | Précision du contexte | Fidélité | Pertinence | Réponses | Pièges refusés |
|---|---|---|---|---|---|---|---|
| 1. Départ (vectoriel, 3 chunks) | 0,57 puis 0,64 | 0,93 | 0,73 | 1,00 | 0,79 | 14 sur 16 | 3 puis 1 |
| 2. Avec reranker | 0,71 | 0,93 | 0,92 | 1,00 | 0,80 | 14 sur 16 | 2 |
| 3. Sous contrôle (reranker, citations vérifiées, refus par seuil) | 0,71 puis 0,64 | 0,93 | 0,92 | 1,00 puis 0,96 | 0,80 | 12 à 13 sur 16 | 2 |

Lecture :
- Le reranker améliore la précision du contexte (0,73 à 0,92) et l'exactitude d'environ 0,07 à 0,14. Le rappel du contexte ne bouge pas (0,93) : les bons chunks étaient déjà dans les 3 premiers, le reranker les classe mieux.
- La version sous contrôle refuse plus, donc répond à moins de questions. Sa fidélité peut rester sous 1 (0,96) : une citation vérifiée prouve que l'extrait existe, pas que la réponse en découle.
- Sur 16 questions, l'écart entre deux exécutions atteint 0,07 d'exactitude et 2 pièges. Un écart de moins de 0,1 n'est pas significatif.
