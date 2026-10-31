# Module 5 : Canaux et gouvernance

```
Canal (WhatsApp)  →  adaptateur  →  passerelle  →  cœur de l'agent (graphe du module 3)
                                                      │                 └─ tools, MCP (module 4)
                                                      └─ interface conseiller (validation, échange)
```

| Dossier | Description |
|---|---|
| `tp1_validation/` | Mettre en pause une régularisation, la soumettre au conseiller, puis reprendre selon sa décision |
| `tp2_cout/` | Calculer le coût mensuel de 1 000 conversations quotidiennes et l'effet du cache de prompt |

## Le service

| Dossier | Contenu |
|---|---|
| `socle/` | `assistant.py` (agent, garde-fous, reprise), `gateway.py` (code commun aux canaux), `guardrails.py`, `history.py`, `monitoring.py`, `tools.py` |
| `service/` | `service.py` (FastAPI) et `channels/whatsapp.py` |

```bash
cd 05_canaux_gouvernance/service
uv run uvicorn service:app --port 8000
```

- `/conseiller` : interface conseiller, accessible uniquement depuis la machine du service.
- `/health` et `/metriques` : état du service et indicateurs.
- WhatsApp démarre si `WA_TOKEN`, `WA_PHONE_NUMBER_ID` et `WA_VERIFY_TOKEN` sont renseignés.
- Langfuse (facultatif) reçoit les traces après masquage des numéros, e-mails et codes. Sans clés, `monitoring.py` écrit dans un fichier JSONL.

## Mémoire des conversations

- `history.py` enregistre les échanges dans `service/conversations.db` (SQLite), par numéro d'expéditeur. `CONVERSATIONS_DB` change l'emplacement.
- Au-delà de 6 000 caractères, les anciens messages sont résumés ; le résumé et les 6 derniers messages restent dans le contexte.
- `/reset` efface l'historique de l'expéditeur. Les données personnelles sont masquées avant enregistrement.

## Limites

- Un canal n'authentifie pas un client. `CLIENT_PAR_DEFAUT` (par exemple `CLI-0002`) désigne le client de tout expéditeur inconnu ; sans elle, `/client` sert à s'identifier.
- Les garde-fous reposent sur des expressions régulières : une reformulation peut les contourner.
- La base est une copie de travail dans le dossier temporaire, partagée avec les autres modules.
