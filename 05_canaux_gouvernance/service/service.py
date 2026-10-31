"""Service de l'assistant Lagune Banque : un cœur d'agent, des adaptateurs de canal, une interface conseiller.

Lancement, depuis 05_canaux_gouvernance/service :
    uv run uvicorn service:app --port 8000
"""
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "socle"))
sys.path.insert(0, str(HERE))

from dotenv import load_dotenv

for dossier in [HERE, *HERE.parents]:                     # le .env de la racine du dépôt sert à tous les modules
    if (dossier / ".env").exists():
        load_dotenv(dossier / ".env")
        break

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

import monitoring
from channels import whatsapp
from assistant import Assistant
from history import History
from gateway import Gateway


class Decision(BaseModel):
    approuve: bool
    conseiller: str
    motif: str = ""


class TakeOver(BaseModel):
    conseiller: str


class AdvisorMessage(BaseModel):
    texte: str


ADVISOR_PAGE = (HERE / "conseiller.html").read_text(encoding="utf-8")


def create_app(assistant: Assistant | None = None) -> FastAPI:
    # un fichier SQLite local : les conversations (une par numéro) survivent au redémarrage du service
    assistant = assistant or Assistant(history=History(os.getenv("CONVERSATIONS_DB") or str(HERE / "conversations.db")))
    channels = {}
    if whatsapp.configure():
        wa_channel = whatsapp.WhatsAppChannel()
        channels["whatsapp"] = wa_channel
    gateway = Gateway(assistant, channels)

    def local_only(requete: Request):
        """L'interface conseiller reste sur la machine du service : une requête qui passe par le tunnel (ngrok) est refusée."""
        hote = (requete.headers.get("host") or "").rsplit(":", 1)[0].strip("[]")
        if requete.headers.get("x-forwarded-for") or requete.headers.get("forwarded") or hote not in ("localhost", "127.0.0.1", "::1"):
            raise HTTPException(status_code=403, detail="Interface conseiller réservée à la machine locale.")

    @asynccontextmanager
    async def lifespan(app):
        yield
        monitoring.clear_langfuse()

    app = FastAPI(title="Assistant Lagune Banque", lifespan=lifespan)
    app.state.gateway = gateway
    if "whatsapp" in channels:
        app.include_router(whatsapp.router(gateway, wa_channel))

    @app.get("/health")
    async def health():
        return {"statut": "ok", "canaux": list(channels), "langfuse": monitoring.langfuse_enabled(),
                "modele": os.getenv("MODELE")}

    @app.get("/metriques")
    async def metrics():
        return gateway.metrics.summary()

    @app.get("/conseiller", response_class=HTMLResponse, dependencies=[Depends(local_only)])
    async def advisor_page():
        return ADVISOR_PAGE

    @app.get("/conseiller/validations", dependencies=[Depends(local_only)])
    async def validations():
        return gateway.pending()

    @app.get("/conseiller/transferts", dependencies=[Depends(local_only)])
    async def handoffs():
        return gateway.open_handoffs()

    @app.post("/conseiller/transferts/{reference}/prise-en-charge", dependencies=[Depends(local_only)])
    async def take_over(reference: str, p: TakeOver):
        try:
            texte = await gateway.take_over(reference, p.conseiller)
        except LookupError as e:
            raise HTTPException(status_code=404, detail=str(e))
        return {"statut": "pris en charge", "message_au_client": texte}

    @app.post("/conseiller/transferts/{reference}/message", dependencies=[Depends(local_only)])
    async def message(reference: str, m: AdvisorMessage):
        if not m.texte.strip():
            raise HTTPException(status_code=400, detail="Message vide.")
        try:
            await gateway.advisor_message(reference, m.texte.strip())
        except LookupError as e:
            raise HTTPException(status_code=404, detail=str(e))
        return {"statut": "envoyé"}

    @app.post("/conseiller/transferts/{reference}/cloture", dependencies=[Depends(local_only)])
    async def close_handoff(reference: str):
        try:
            texte = await gateway.close_handoff(reference)
        except LookupError as e:
            raise HTTPException(status_code=404, detail=str(e))
        return {"statut": "clos", "message_au_client": texte}

    @app.post("/conseiller/validations/{session:path}/decision", dependencies=[Depends(local_only)])
    async def decision(session: str, d: Decision):
        try:
            texte = await gateway.decide(session, d.approuve, d.conseiller, d.motif)
        except LookupError as e:
            raise HTTPException(status_code=404, detail=str(e))
        return {"statut": "decision enregistrée", "message_au_client": texte}

    return app


app = create_app()
