# Module 1 : fondamentaux de la GenAI et prompting

| Ordre | Notebook | Ce qu'il montre | Mesure |
|---|---|---|---|
| 1 | `tp3_iterate_prompt/` | TP : améliorer un prompt en trois versions et comparer leurs résultats | bonnes demandes et tokens par version |
| 2 | `tp1_extraction_json/` | TP : extraire une réclamation avec un schéma Pydantic | champs justes, latence et coût estimé pour 1 000 requêtes |
| 3 | `tp2_function_calling/` | TP : implémenter la boucle d'appel d'outil sur des données de Lagune Banque | comportement sur quatre scénarios |

## Prérequis

- `.env` : `LLM_API_KEY` et `MODELE`.
- Le TP2 lit `data/banque.db`.
