"""Service de l'assistant Lagune Banque : un cœur d'agent, des adaptateurs de canal, une interface conseiller.

Lancement, depuis 05_canaux_gouvernance/service :
    uv run uvicorn service:app --port 8000
"""
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent / "socle"))
sys.path.insert(0, str(ICI))

from dotenv import load_dotenv

for dossier in [ICI, *ICI.parents]:                       # le .env de la racine du dépôt sert à tous les modules
    if (dossier / ".env").exists():
        load_dotenv(dossier / ".env")
        break

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

import suivi
from canaux import whatsapp
from coeur import Assistant
from historique import History
from passerelle import Passerelle


class Decision(BaseModel):
    approuve: bool
    conseiller: str
    motif: str = ""


PAGE_CONSEILLER = (ICI / "conseiller.html").read_text(encoding="utf-8")


def creer_app(assistant: Assistant | None = None) -> FastAPI:
    # un fichier SQLite local : les conversations (une par numéro) survivent au redémarrage du service
    assistant = assistant or Assistant(history=History(os.getenv("CONVERSATIONS_DB") or str(ICI / "conversations.db")))
    canaux = {}
    if whatsapp.configure():
        canal_wa = whatsapp.CanalWhatsApp()
        canaux["whatsapp"] = canal_wa
    passerelle = Passerelle(assistant, canaux)

    def conseiller(requete: Request):
        """L'interface conseiller reste sur la machine du service : une requête qui passe par le tunnel (ngrok) est refusée."""
        hote = (requete.headers.get("host") or "").rsplit(":", 1)[0].strip("[]")
        if requete.headers.get("x-forwarded-for") or requete.headers.get("forwarded") or hote not in ("localhost", "127.0.0.1", "::1"):
            raise HTTPException(status_code=403, detail="Interface conseiller réservée à la machine locale.")

    @asynccontextmanager
    async def lifespan(app):
        yield
        suivi.clear_langfuse()

    app = FastAPI(title="Assistant Lagune Banque", lifespan=lifespan)
    app.state.passerelle = passerelle
    if "whatsapp" in canaux:
        app.include_router(whatsapp.routeur(passerelle, canal_wa))

    @app.get("/health")
    async def health():
        return {"statut": "ok", "canaux": list(canaux), "langfuse": suivi.langfuse_enabled(),
                "modele": os.getenv("MODELE")}

    @app.get("/metriques")
    async def metriques():
        return passerelle.metriques.summary()

    @app.get("/conseiller", response_class=HTMLResponse, dependencies=[Depends(conseiller)])
    async def page_conseiller():
        return PAGE_CONSEILLER

    @app.get("/conseiller/validations", dependencies=[Depends(conseiller)])
    async def validations():
        return passerelle.en_attente()

    @app.post("/conseiller/validations/{session:path}/decision", dependencies=[Depends(conseiller)])
    async def decision(session: str, d: Decision):
        try:
            texte = await passerelle.decide(session, d.approuve, d.conseiller, d.motif)
        except LookupError as e:
            raise HTTPException(status_code=404, detail=str(e))
        return {"statut": "decision enregistrée", "message_au_client": texte}

    return app


app = creer_app()
