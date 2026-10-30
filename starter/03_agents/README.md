# Module 3 — Agents avec LangChain et LangGraph

Le module construit un agent capable d'enquêter sur un remboursement Lagune Money qui n'apparaît pas dans le dossier du client (données fictives). Les notebooks ajoutent progressivement les outils, la mémoire, les contrôles de sécurité, l'orchestration et l'observabilité.

Les démos sont présentées par le formateur ; les TP sont à compléter (`# TODO`). Chaque TP se termine par un contrôle automatique et une cellule permettant de brancher l'agent sur l'interface Gradio.

| Ordre | Notebook | Notion travaillée | Indicateur observé |
|---|---|---|---|
| 1 | `demos/demo1_tool_descriptions/` | Effet de descriptions d'outils précises, vagues ou ambiguës sur le choix du modèle | outils choisis en premier sur 17 questions |
| 2 | `tp1_agent_tools/` | Écrire et décrire les outils, puis définir la procédure de l'agent | outils appelés et état de la base pour trois clients |
| 3 | `demos/demo2_context_growth/` | Comparer l'historique complet, sa troncature et son résumé | tokens transmis et informations conservées |
| 4 | `tp2_memory/` | Ajouter un checkpointer et un `thread_id`, puis limiter ou résumer l'historique | éléments retenus et tokens par appel |
| 5 | `tp3_security/` | Ajouter une validation humaine et des contrôles contre les injections directes et indirectes | attaques réussies avant et après les parades |
| 6 | `tp4_langgraph/` | Construire un graphe avec routeur, cinq parcours, validation et transfert au conseiller | exactitude du routeur, trajectoires et dossiers |
| 7 | `demos/demo3_trace_langfuse/` | Lire les outils appelés, leurs arguments et résultats, la latence et les tokens | inspection des traces |
| 8 | `tp5_trace_debugging/` | Diagnostiquer une boucle, un mauvais outil ou une date non fournie à partir des traces | causes identifiées et scénarios corrigés |
| 9 | `demos/demo4_gradio_assistant/` | Afficher les appels d'outils de l'agent dans une interface Gradio | inspection des appels dans l'interface |
| Bonus | `bonus_supervisor/` | Comparer un agent unique à un superviseur et deux agents spécialisés | appels au modèle et durée |

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

## Lancer

```bash
cd starter
uv sync
uv run jupyter lab
```

Renseignez dans `.env` : `LLM_API_KEY` et `MODELE`. Chaque notebook appelle le vrai modèle : la durée de chaque notebook est indiquée dans `../data/evaluation/resultats_de_reference_agents.md`. Les résultats varient légèrement d'une exécution à l'autre : les contrôles portent sur l'état de la base et sur les tools appelés, pas sur le texte des réponses.

Langfuse est facultatif : la démo 3 en a besoin pour afficher les traces dans l'interface. Les autres notebooks fonctionnent sans Langfuse ; les détails de configuration figurent dans `../README.md`.
