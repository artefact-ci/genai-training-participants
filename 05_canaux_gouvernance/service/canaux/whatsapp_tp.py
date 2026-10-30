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
        """Envoie `texte` au numéro `utilisateur`. WhatsApp limite un message à 4096 caractères.

        TODO 2 : POST sur self.url, avec self.entetes, via httpx.AsyncClient. Le JSON est
        {"messaging_product": "whatsapp", "to": utilisateur, "type": "text", "text": {"body": texte}}.
        Découpez les textes de plus de 4096 caractères et affichez l'erreur si le code de retour est >= 400.
        """
        raise NotImplementedError("TODO 2")
