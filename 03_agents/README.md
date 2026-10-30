# Module 3 : Agents avec LangChain et LangGraph

Un agent enquête sur un remboursement Lagune Money absent du dossier d'un client (données fictives). Chaque TP se termine par un contrôle automatique et une cellule Gradio.

| Ordre | Notebook | Notion travaillée | Indicateur observé |
|---|---|---|---|
| 1 | `tp1_agent_tools/` | Écrire et décrire les outils, puis définir la procédure de l'agent | outils appelés et état de la base pour trois clients |
| 2 | `tp2_memory/` | Ajouter un checkpointer et un `thread_id`, puis limiter ou résumer l'historique | éléments retenus et tokens par appel |
| 3 | `tp3_security/` | Ajouter une validation humaine et des contrôles contre les injections directes et indirectes | attaques réussies avant et après les parades |
| 4 | `tp4_langgraph/` | Construire un graphe avec routeur, cinq parcours, validation et transfert au conseiller | exactitude du routeur, trajectoires et dossiers |
| 5 | `tp5_trace_debugging/` | Diagnostiquer une boucle, un mauvais outil ou une date non fournie à partir des traces | causes identifiées et scénarios corrigés |

## Le socle

Dans `socle/`, importé par tous les notebooks à partir du TP2 (le TP1 en reprend une partie et écrit le reste) :

| Fichier | Contenu |
|---|---|
| `base.py` | chemins, copie de travail de la base, contexte d'exécution (`Context`), modèle (`new_model`), affichage d'une conversation (`print_trace`), tools appelés (`tools_called`), appels au modèle (`model_calls`) |
| `business.py` | fonctions métier sans modèle : lecture des prêts, des échéances et de la documentation, création d'une réclamation, régularisation |
| `tools.py` | solution du TP1 : les sept tools, `TOOLS`, `SYSTEM_PROMPT` |
| `tracing.py` | collecte locale des appels (tool, arguments, résultat, durée, tokens) |
| `chat.py` | branche un agent sur l'interface Gradio de `code_partage/front.py` |

`tools.py` contient la solution du TP1 : ne l'ouvrez qu'après ce TP.

## Les sept tools

| Tool | Rôle | Risque |
|---|---|---|
| `search_docs` | Recherche dans la documentation (index du module 2) | Lecture |
| `get_customer_loans` | Prêts du client identifié | Lecture bancaire |
| `get_schedule` | Échéancier | Lecture bancaire |
| `check_lm_transaction` | Remboursements Lagune Money autour d'une date | Lecture |
| `check_platform_incident` | Incident de la plateforme à une date et une heure | Lecture |
| `create_claim` | Réclamation avec dossier pour un conseiller | Faible |
| `propose_regularisation` | Rattachement, annulation des frais, levée de la suspension | Incidence financière : validation par un conseiller |

Le `client_id` n'est jamais un paramètre d'un tool : il vient du contexte d'exécution, rempli par l'application après identification. La table de la base qui contient les transactions Lagune Money s'appelle `transactions_om`.

## Prérequis

`.env` : `LLM_API_KEY`, `MODELE` et `MODELE_EMBEDDING` (pour `search_docs`). Chaque notebook appelle le vrai modèle. Les résultats varient d'une exécution à l'autre : les contrôles portent sur l'état de la base et sur les tools appelés, pas sur le texte des réponses.

Langfuse est facultatif : sans clés, le TP5 utilise la collecte locale de `socle/tracing.py`. Configuration : section Langfuse du [README](../README.md).
