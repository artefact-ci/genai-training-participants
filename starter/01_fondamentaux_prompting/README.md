# Module 1 : fondamentaux de la GenAI et prompting

Notions couvertes :
- les tokens et le contexte d'un modèle ;
- les paramètres de génération (`temperature`, `seed`, `max_tokens`) ;
- les causes de l'hallucination et les limites du modèle ;
- la rédaction d'un prompt mesurable et exploitable ;
- la production de JSON fiable en code ;
- l'appel de fonction par un modèle.

Les notebooks de travail sont à compléter (`# TODO`).

| Ordre | Notebook | Ce qu'il montre | Mesure |
|---|---|---|---|
| 1 | `demos/demo1_tokens_context/` | tokenisation, coûts d'entrée et de sortie, accumulation de l'historique | tokens et coût d'une conversation de huit tours |
| 2 | `demos/demo2_sampling/` | effets de `temperature`, `top_p` et `seed`, puis limite de `max_tokens` | réponses produites avec deux modèles |
| 3 | `demos/demo3_hallucination/` | comparaison d'une réponse sans documentation et d'une réponse avec source consultable | réponses, passage source et tokens d'entrée |
| 4 | `demos/demo4_prompting/` | comparaison de techniques de prompting sur la classification et le calcul | exactitude par technique |
| 5 | `tp3_iterate_prompt/` | TP : améliorer un prompt en trois versions et comparer leurs résultats | bonnes demandes et tokens par version |
| 6 | `demos/demo5_structured_output/` | extraction de données : JSON demandé dans le prompt ou imposé par un schéma | sortie obtenue dans chaque cas |
| 7 | `tp1_extraction_json/` | TP : extraire une réclamation avec un schéma Pydantic | champs justes, latence et coût estimé pour 1 000 requêtes |
| 8 | `demos/demo6_function_calling/` | demande d'appel d'outil par le modèle, puis exécution par le code | appel d'outil, étape par étape |
| 9 | `tp2_function_calling/` | TP : implémenter la boucle d'appel d'outil sur des données de Lagune Banque | comportement sur quatre scénarios |

## Lancer

```bash
cd starter
uv sync
uv run jupyter lab
```

Renseignez dans `.env` : `LLM_API_KEY` et `MODELE`. La démo 3 charge la documentation de `data/corpus/`. Le TP2 lit `data/banque.db`.
