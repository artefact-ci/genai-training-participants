# Formation Agents IA & AI Engineering

Le fil rouge est un assistant support client pour Lagune Banque (données fictives).

## Prérequis

- [uv](https://docs.astral.sh/uv/getting-started/installation/) (il installe aussi Python 3.11).
- Git.
- Une clé d'API LLM.
- Docker, pour Weaviate : à installer avant le jour 1. Si Weaviate est injoignable, une base en mémoire prend le relais, mais l'index n'est pas conservé d'un lancement à l'autre.

## Installation

```bash
git clone <url>
cd <dossier du dépôt>
cp .env.example .env   # puis renseignez vos clés
uv sync
uv run scripts/check_env.py
uv run jupyter lab
```

Renseignez dans `.env` :

- `LLM_API_KEY` et `MODELE` : obligatoires. `MODELE_2` (facultatif) sert à comparer un second modèle au module 1.
- `MODELE_EMBEDDING` : modèle d'embedding (module 2, et tool `search_docs` des modules 3 à 5), par exemple `text-embedding-3-small`.
- `MODELE_RERANK`, `RERANK_API_KEY` et `RERANK_API_BASE` : le reranker du module 2 (recherche hybride et reranking). Le modèle est Cohere Rerank déployé sur Azure AI Foundry : `MODELE_RERANK=azure_ai/<nom du déploiement>` et `RERANK_API_BASE=https://<ressource>.services.ai.azure.com`.

`check_env.py` doit afficher `OK`. Sinon, son message indique quoi corriger.

## Interface Gradio

Le fil rouge est un « chat avec vos données ». `code_partage/front.py` fournit l'interface de chat, avec son thème : vous n'écrivez pas de front, seulement la fonction qui répond.

| Module | Ce que l'interface montre |
|---|---|
| 3 | Un bloc par tool appelé par l'agent (arguments, résultat, durée). Le client se choisit dans une liste. Chaque TP se termine par une cellule qui branche votre agent sur cette interface |
| 5 | WhatsApp et la page conseiller : le service FastAPI garde son propre front |

Pour brancher votre fonction :

```python
import front

def repondre(message, historique):
    chunks = ...                                         # votre recherche
    etape = front.chunks_block(chunks, duree=0.8)        # ou front.block(titre, texte) pour un bloc libre
    yield [etape]                                          # le bloc s'affiche pendant que le modèle rédige
    yield [etape, gr.ChatMessage(content=reponse)]         # puis la réponse

demo = front.create(repondre, titre="...", description="...", accueil="...", exemples=["..."])
front.launch(demo)                                         # sous la cellule ; navigateur=True pour un onglet
```

- `front.exchanges(historique)` donne les échanges précédents en texte seul. `front.tool_block(appel, resultat)` fabrique le bloc d'un appel de tool.
- Un champ supplémentaire (par exemple le client identifié) se passe avec `champs=[gr.Dropdown(...)]`. Sa valeur arrive à la fonction après `message` et `historique`.
- Gradio 6 prend le thème et le CSS au lancement, pas à la création : c'est `front.launch` qui les applique.
- N'utilisez pas `share=True` : il crée un lien public vers une interface qui consomme vos clés.
- Fermez l'interface avec `demo.close()`. Une interface restée ouverte garde le port 7860, et la suivante prend le port d'après.

## Langfuse Cloud (facultatif)

Langfuse affiche les traces d'un agent ou d'un RAG : les décisions prises, leur ordre, la durée et les tokens.
Il sert à plusieurs endroits :

- Module 3 : TP5 `03_agents/tp5_trace_debugging`.
- Module 5 : le service envoie ses traces.

Sans clés Langfuse, le code n'envoie rien et ne plante pas. Le TP5 utilise alors sa collecte locale (`03_agents/socle/tracing.py`) et le service écrit ses indicateurs dans un fichier.

Mise en route :

1. Créez un compte Hobby sur <https://cloud.langfuse.com> (gratuit, sans carte bancaire, 50 000 unités par mois), puis un projet.
2. Dans *Settings > API Keys*, copiez les deux clés dans `.env` : `LANGFUSE_PUBLIC_KEY` et `LANGFUSE_SECRET_KEY`.
3. Réglez `LANGFUSE_HOST` sur la région du projet : `https://cloud.langfuse.com` (Europe, valeur par défaut) ou `https://us.cloud.langfuse.com` (États-Unis).
   Une clé n'est valide que dans la région de son projet.
4. Lancez `uv run scripts/verifier_langfuse.py`. Il doit afficher `OK`.

Le code masque les numéros, les e-mails et les codes de vérification avant d'envoyer une trace (`code_partage/observabilite.py`).
Le plan gratuit conserve les données 30 jours et accepte 2 utilisateurs par projet.

### Nommer ses traces

Sans nom, Langfuse affiche celui de l'exécution racine : `LangGraph` pour un graphe ou un agent, `ChatLiteLLM` pour un appel direct au modèle.
Les graphiques « Use Cases » regroupent alors tout sous ces deux noms. Pour les distinguer, passez `nom` à `langfuse_callbacks` :

```python
rappels, meta = langfuse_callbacks(session_id="tp5", utilisateur="CLI-0002", tags=["tp5"], nom="m3-tp5-traces")
agent.invoke(..., config={"callbacks": rappels, "metadata": meta})
```

Convention : `m<module>-<usage>`, en minuscules et avec des tirets.

| Où | Nom de la trace | Session | Utilisateur | Tags |
|---|---|---|---|---|
| TP5 du module 3 | `m3-tp5-traces` | `tp5` | le client du scénario | `tp5` |
| Interface Gradio du module 3 | `m3-front-agent` | `front-<empreinte>` | le client choisi | `front`, `m3` |
| Service du module 5 | `m5-assistant-lagune` | `<canal>-<empreinte>-<n>` | `CLI-xxxx` | `canal:whatsapp` |

FastMCP envoie aussi ses propres spans OpenTelemetry. `observabilite.py` les bloque (`blocked_instrumentation_scopes=["fastmcp"]`) : sans cela, chaque tool MCP apparaîtrait comme une trace séparée, sans session ni client.

Pour séparer plusieurs usages dans un même projet, définissez `LANGFUSE_TRACING_ENVIRONMENT` dans `.env` (par exemple `formation` ou `demo`). Langfuse l'affiche comme filtre.

Le numéro de téléphone ou le `chat_id` n'est jamais envoyé : l'utilisateur est le client (`CLI-xxxx`) et la session porte une empreinte non réversible du numéro (`pseudonym()` dans `code_partage/observabilite.py`).

### Afficher le prix des modèles

Langfuse calcule le prix d'une génération à partir de ses tokens et d'une définition de modèle. Les modèles passent par LiteLLM avec un préfixe de fournisseur
(`gemini/gemini-3.5-flash-lite`), que les définitions prédéfinies de Langfuse n'acceptent pas toujours. Sans définition qui correspond, les tokens s'affichent mais le prix reste vide.

Dans Langfuse, *Settings > Models > Add model definition* :

| Champ | Valeur |
|---|---|
| Nom du modèle | le nom sans préfixe, par exemple `gemini-3.5-flash-lite` |
| Motif de correspondance | `(?i)^(gemini/\|google(ai)?/)?gemini-3\.5-flash-lite$` (écrivez `\|` comme un simple `|`, et `\.` pour un point) |
| Unité | Tokens |
| Prix en entrée et en sortie | prix par million de tokens divisé par 1 000 000 |
| Tokenizer | aucun : le fournisseur renvoie déjà les tokens exacts |

Exemple avec Gemini 3.5 Flash-Lite (tarif payant standard relevé le 27/10/2026, à vérifier sur la page des tarifs de Google) : 0,30 $ par million en entrée, soit `0.0000003`, et 2,50 $ par million en sortie, soit `0.0000025`.
Pour un autre modèle (`MODELE` dans `.env`), reprenez le même motif avec son nom.

La définition ne s'applique qu'aux nouvelles traces : relancez la démo après l'avoir créée.

### Lire les traces par l'API

Le dépôt n'appelle pas l'API de lecture de Langfuse : il n'envoie que des traces. Si vous écrivez un script de lecture, n'utilisez pas `client.api.trace.list` (route `GET /api/public/traces`, retirée le 16/11/2026). Utilisez `client.api.observations.get_many`, avec `fields="core,basic,trace_context,usage"` pour obtenir le nom de trace, la session, l'utilisateur, les tags et le prix.
