# Module 3 : Agents avec LangChain et LangGraph

| Notebook | Description |
|---|---|
| `tp1_agent_tools/` | Écrire et décrire les outils, puis définir la procédure de l'agent |
| `tp2_memory/` | Ajouter un checkpointer et un `thread_id`, puis limiter ou résumer l'historique |
| `tp3_security/` | Ajouter une validation humaine et des contrôles contre les injections directes et indirectes |
| `tp4_langgraph/` | Construire un graphe avec routeur, cinq parcours, validation et transfert au conseiller |
| `tp5_trace_debugging/` | Diagnostiquer une boucle, un mauvais outil ou une date manquante à partir des traces |

## Le socle

`socle/`, importé par tous les notebooks à partir du TP2 :

| Fichier | Contenu |
|---|---|
| `base.py` | chemins, copie de travail de la base, contexte d'exécution, modèle, affichage des conversations et des appels |
| `business.py` | fonctions métier sans modèle : prêts, échéances, documentation, réclamation, régularisation |
| `tools.py` | solution du TP1 : les sept tools, `TOOLS`, `SYSTEM_PROMPT` |
| `tracing.py` | collecte locale des appels (tool, arguments, résultat, durée, tokens) |
| `chat.py` | branche un agent sur l'interface Gradio de `code_partage/front.py` |

## Les sept tools

| Tool | Rôle |
|---|---|
| `search_docs` | recherche dans la documentation (index du module 2) |
| `get_customer_loans` | prêts du client identifié |
| `get_schedule` | échéancier |
| `check_lm_transaction` | remboursements Lagune Money autour d'une date |
| `check_platform_incident` | incident de la plateforme à une date et une heure |
| `create_claim` | réclamation avec dossier pour un conseiller |
| `propose_regularisation` | rattachement, annulation des frais, levée de la suspension, après validation d'un conseiller |

Le `client_id` n'est jamais un paramètre d'un tool : il vient du contexte d'exécution. Les transactions Lagune Money sont dans la table `transactions_om`.

## Prérequis

- `.env` : `LLM_API_KEY`, `MODELE` et `MODELE_EMBEDDING` (pour `search_docs`).
- Les résultats varient d'une exécution à l'autre : les contrôles portent sur l'état de la base et les tools appelés.
- Langfuse est facultatif : sans clés, le TP5 utilise `socle/tracing.py`. Configuration : [README](../README.md).
