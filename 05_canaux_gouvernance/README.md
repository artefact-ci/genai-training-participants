# Module 5 : Canaux et gouvernance

L'assistant de Lagune Banque (données fictives) sur des canaux de messagerie, via un service FastAPI.

```
Canal (WhatsApp)  →  adaptateur  →  passerelle  →  cœur de l'agent (graphe du module 3)
                                                      │                 └─ tools, MCP (module 4)
                                                      └─ interface conseiller (validation, échange)
```

| Ordre | Dossier | Notion travaillée |
|---|---|---|
| 1 | `tp1_validation/` | Mettre en pause une régularisation, présenter son dossier au conseiller, puis reprendre selon sa décision |
| 2 | `tp2_cout/` | Calculer le coût mensuel de 1 000 conversations quotidiennes et estimer l'effet du cache de prompt |

## Structure du service

| Dossier | Contenu |
|---|---|
| `socle/` | `assistant.py` (agent, garde-fous, reprise), `gateway.py` (code commun aux canaux), `guardrails.py`, `history.py` (conversations), `monitoring.py` (tokens, coût, Langfuse), `tools.py` |
| `service/` | `service.py` (FastAPI) et `channels/whatsapp.py`, l'adaptateur WhatsApp |

## Lancer le service

```bash
cd 05_canaux_gouvernance/service
uv run uvicorn service:app --port 8000
```

- `http://localhost:8000/conseiller` : interface conseiller. Elle n'est ouverte que depuis la machine qui exécute le service : une requête passant par le tunnel est refusée.
- `/health` et `/metriques` : état du service et indicateurs.

## Canaux

- WhatsApp, présenté en démo par le formateur : il faut un compte professionnel validé, des modèles de messages pré-approuvés,
  et la réponse doit partir dans les 24 heures qui suivent le dernier message du client. Le canal ne démarre que si `WA_TOKEN`,
  `WA_PHONE_NUMBER_ID` et `WA_VERIFY_TOKEN` sont renseignés.

## Suivi avec Langfuse (facultatif)

Avec `LANGFUSE_PUBLIC_KEY` et `LANGFUSE_SECRET_KEY`, le service envoie ses traces à Langfuse après avoir masqué numéros, e-mails et codes ([mise en route](../README.md)). Sans elles, `monitoring.py` écrit les indicateurs dans un fichier JSONL.

## Mémoire des conversations

`history.py` enregistre chaque échange dans un fichier SQLite local (`service/conversations.db`, ignoré par Git). La clé est l'identifiant de l'expéditeur : le numéro de téléphone WhatsApp. Le service garde donc le fil d'une conversation après un redémarrage.

- À chaque message, l'agent reçoit l'historique de l'expéditeur. Un message court (« et pour l'Express+ ? ») est compris grâce aux échanges précédents.
- Quand la conversation dépasse 6 000 caractères, les anciens messages sont résumés par le modèle. Le résumé et les 6 derniers messages restent dans le contexte.
- `/reset` efface l'historique de l'expéditeur.
- `CONVERSATIONS_DB` change l'emplacement du fichier.
- Les données personnelles sont masquées avant d'être enregistrées.

## Limites

- Un canal n'authentifie pas un client bancaire. Dans la formation, l'identification est simplifiée : `CLIENT_PAR_DEFAUT` (par exemple `CLI-0002`) désigne le client de tout expéditeur inconnu ; sans elle, la commande `/client` sert à s'identifier. En production, il faut une authentification réelle.
- Les garde-fous reposent sur des motifs (expressions régulières). Une reformulation peut les contourner.
- La base est une copie de travail dans le dossier temporaire, partagée avec les autres modules.
