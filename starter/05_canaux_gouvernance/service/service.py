"""Service de l'assistant Lagune Banque : un cœur d'agent, des adaptateurs de canal, une interface conseiller.

Lancement, depuis starter/05_canaux_gouvernance/service :
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

for dossier in [ICI, *ICI.parents]:                       # le .env de starter/ sert à tous les modules
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


PAGE_CONSEILLER = """<!doctype html><meta charset="utf-8"><title>Conseiller – validations</title>
<style>body{font:16px system-ui;max-width:760px;margin:2rem auto;padding:0 1rem}.carte{border:1px solid #ccc;border-radius:8px;padding:1rem;margin:1rem 0}
dl{display:grid;grid-template-columns:max-content 1fr;gap:.3rem 1rem;margin:.6rem 0}dt{color:#555}dd{margin:0}
button{margin-right:.5rem;padding:.4rem .8rem}.ok{background:#e7f6ea;border:1px solid #9bd3a7;border-radius:8px;padding:.7rem;margin:1rem 0}</style>
<h1>Validations en attente</h1>
<p>Conseiller : <input id="qui" value="CONS-01" size="8"> <button onclick="charge()">Actualiser</button></p>
<div id="resultat"></div>
<div id="liste"></div>
<script>
const LIBELLES = {action: "Action demandée", echeance_id: "Échéance", transaction_id: "Transaction Lagune Money", incident_id: "Incident de la plateforme",
                  justification: "Justification de l'assistant"};
const ACTIONS = {propose_regularisation: "Régularisation : rattacher le paiement, annuler les frais de retard, lever la suspension"};
function ligne(dl, libelle, valeur){ const dt = document.createElement("dt"), dd = document.createElement("dd");
  dt.textContent = libelle; dd.textContent = valeur; dl.append(dt, dd); }
async function charge(){ const r = await fetch("/conseiller/validations"); const l = document.getElementById("liste");
  if (!r.ok){ l.textContent = "Accès refusé : cette page n'est ouverte que depuis la machine qui exécute le service."; return; }
  const v = await r.json(); l.textContent = v.length ? "" : "Rien en attente.";
  v.forEach(x => { const d = document.createElement("div"); d.className = "carte";
    const titre = document.createElement("b"); titre.textContent = "Client " + x.client_id + " (" + x.canal + ")"; d.append(titre);
    const dl = document.createElement("dl");
    for (const [cle, valeur] of Object.entries(x.dossier)){ if (valeur === null || valeur === "") continue;
      ligne(dl, LIBELLES[cle] || cle, cle === "action" ? (ACTIONS[valeur] || valeur) : valeur); }
    d.append(dl);
    for (const [lib, ok] of [["Valider", true], ["Refuser", false]]){ const b = document.createElement("button"); b.textContent = lib;
      b.onclick = async () => { const motif = ok ? "" : (prompt("Motif du refus ?") || "");
        const rep = await fetch("/conseiller/validations/" + encodeURIComponent(x.session) + "/decision", {method: "POST",
          headers: {"Content-Type": "application/json"}, body: JSON.stringify({approuve: ok, conseiller: document.getElementById("qui").value, motif})});
        const res = document.getElementById("resultat"); res.className = "ok";
        res.textContent = rep.ok ? (ok ? "Validé. " : "Refusé. ") + "Message envoyé au client : " + (await rep.json()).message_au_client : "Erreur : " + (await rep.text());
        charge(); };
      d.append(b); }
    document.getElementById("liste").append(d); }); }
charge();
</script>"""


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
