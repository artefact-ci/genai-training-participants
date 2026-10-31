"""Canal WhatsApp (Cloud API de Meta).

Le fichier suit le trajet d'un message, en quatre blocs :

1. Configuration : variables d'environnement.
2. Envoi : appels à l'API Graph (texte, accusé de lecture).
3. Sécurité : vérification de la signature des webhooks.
4. Webhook : vérification de l'URL par Meta, puis réception des messages.

Contraintes de WhatsApp : compte professionnel validé, modèle de message pré-approuvé pour écrire en premier,
réponse libre pendant 24 heures après le dernier message du client.
"""
import asyncio
import hashlib
import hmac
import json
import os

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

from gateway import Message

# ------------------------------------------------------------------ 1. Configuration
VARIABLES = ("WA_TOKEN", "WA_PHONE_NUMBER_ID", "WA_VERIFY_TOKEN")
VERSION_API = "v25.0"
LIMITE_MESSAGE = 4096          # caractères maximum dans un message WhatsApp


def configure() -> bool:
    """True si les trois variables obligatoires sont renseignées."""
    return all(os.getenv(v) for v in VARIABLES)


# ------------------------------------------------------------------ 2. Envoi
class WhatsAppChannel:
    nom = "whatsapp"

    def __init__(self):
        manquantes = [v for v in VARIABLES if not os.getenv(v)]
        if manquantes:
            raise RuntimeError(f"WhatsApp : variable(s) manquante(s) : {', '.join(manquantes)}")
        self.url = f"https://graph.facebook.com/{VERSION_API}/{os.environ['WA_PHONE_NUMBER_ID']}/messages"
        self.entetes = {"Authorization": f"Bearer {os.environ['WA_TOKEN']}"}

    async def _post(self, payload: dict) -> None:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(self.url, headers=self.entetes, json=payload)
        if r.status_code >= 400:
            print("Erreur WhatsApp :", r.status_code, r.text)

    async def send(self, utilisateur: str, texte: str) -> None:
        """Envoie un texte, découpé si besoin."""
        for i in range(0, max(len(texte), 1), LIMITE_MESSAGE):
            await self._post({"messaging_product": "whatsapp", "to": utilisateur, "type": "text",
                              "text": {"body": texte[i:i + LIMITE_MESSAGE]}})

    async def mark_read(self, message_id: str) -> None:
        """Affiche les coches bleues chez le client."""
        await self._post({"messaging_product": "whatsapp", "status": "read", "message_id": message_id})


# ------------------------------------------------------------------ 3. Sécurité
def valid_signature(corps: bytes, entete: str | None) -> bool:
    """Compare la signature HMAC-SHA256 envoyée par Meta (en-tête X-Hub-Signature-256) à celle du corps reçu."""
    secret = os.getenv("META_APP_SECRET", "")
    if not secret:
        return True                                                  # vérification désactivée : voir l'avertissement au démarrage
    if not entete or not entete.startswith("sha256="):
        return False
    attendu = hmac.new(secret.encode(), corps, hashlib.sha256).hexdigest()
    return hmac.compare_digest(attendu, entete[len("sha256="):])


# ------------------------------------------------------------------ 4. Webhook
def incoming_messages(donnees: dict) -> list[dict]:
    """Les messages d'un webhook. Les notifications de statut n'en contiennent pas."""
    return [m for entree in donnees.get("entry", []) for changement in entree.get("changes", [])
            for m in changement.get("value", {}).get("messages", [])]


async def _handle(gateway, channel: WhatsAppChannel, m: dict) -> None:
    try:
        await channel.mark_read(m["id"])
        if m.get("type") != "text":
            await channel.send(m["from"], "Je comprends seulement le texte pour l'instant.")
            return
        await gateway.handle(Message("whatsapp", m["from"], m["text"]["body"], m["id"]))
    except Exception as e:                                           # une tâche de fond qui plante ne laisse aucune trace
        print("Erreur WhatsApp :", repr(e))


def router(gateway, channel: WhatsAppChannel) -> APIRouter:
    if not os.getenv("META_APP_SECRET"):
        print("ATTENTION : META_APP_SECRET est absent. La signature des webhooks n'est pas vérifiée.")
    r = APIRouter()

    @r.get("/webhook/whatsapp")
    async def verify(request: Request):
        """Meta appelle cette route à l'enregistrement du webhook et attend `hub.challenge` en retour."""
        q = request.query_params
        if q.get("hub.mode") == "subscribe" and q.get("hub.verify_token") == os.environ["WA_VERIFY_TOKEN"]:
            return PlainTextResponse(q.get("hub.challenge"))
        return PlainTextResponse("refusé", status_code=403)

    @r.post("/webhook/whatsapp")
    async def receive(request: Request):
        corps = await request.body()
        if not valid_signature(corps, request.headers.get("X-Hub-Signature-256")):
            raise HTTPException(status_code=403, detail="Signature invalide")
        for m in incoming_messages(json.loads(corps)):
            asyncio.create_task(_handle(gateway, channel, m))
        return {"status": "ok"}                                      # 200 immédiat : Meta renvoie le message si on tarde

    return r
