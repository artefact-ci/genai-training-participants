"""Adaptateur WhatsApp du TP1 : à compléter.

Il fait les deux traductions d'un adaptateur de canal. Le service utilise `whatsapp.py`, déjà complet : ce fichier-ci sert
à comprendre ce que fait un adaptateur, avec des tests sans réseau.
"""
import httpx

from passerelle import Message

LIMITE_MESSAGE = 4096          # caractères maximum dans un message WhatsApp


class CanalWhatsAppTP:
    nom = "whatsapp"

    def __init__(self, token: str, phone_number_id: str):
        self.url = f"https://graph.facebook.com/v25.0/{phone_number_id}/messages"
        self.entetes = {"Authorization": f"Bearer {token}"}

    def analyser(self, m: dict) -> Message | None:
        """Un message d'un webhook WhatsApp -> un Message. None si ce n'est pas un message texte.

        TODO 1 : `m` ressemble à {"from": "2250700000000", "id": "wamid.ABC", "type": "text", "text": {"body": "Bonjour"}}.
        Renvoyez Message("whatsapp", <from>, <texte>, <id>), ou None si `type` n'est pas "text".
        """
        raise NotImplementedError("TODO 1")

    async def envoyer(self, utilisateur: str, texte: str) -> None:
        """Envoie `texte` au numéro `utilisateur`. WhatsApp limite un message à 4096 caractères : un texte plus long part
        en plusieurs messages. Le découpage et l'appel HTTP sont fournis.
        """
        morceaux = [texte[i:i + LIMITE_MESSAGE] for i in range(0, max(len(texte), 1), LIMITE_MESSAGE)]
        for morceau in morceaux:
            # TODO 2 : traduisez le morceau au format de l'API WhatsApp. Remplacez les deux "" par le numéro du
            # destinataire et par le texte du morceau.
            corps = {"messaging_product": "whatsapp", "to": "", "type": "text", "text": {"body": ""}}
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.post(self.url, headers=self.entetes, json=corps)
            if r.status_code >= 400:
                print("Erreur WhatsApp :", r.status_code, r.text)
