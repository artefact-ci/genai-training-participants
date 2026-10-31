"""Passerelle : tout ce qui est commun à tous les canaux, entre un adaptateur et le cœur de l'agent.

Un adaptateur de canal fait deux choses seulement : transformer un message entrant en `Message`, et envoyer un texte.
La passerelle gère le reste : doublons, limite de débit, un traitement à la fois par utilisateur, identification
par commande (formation), commandes, validation conseiller. Ajouter un canal ne change donc ni la passerelle ni l'agent.
"""
import asyncio
import json
import os
import re
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Optional, Protocol

from outils import connect

import suivi
from coeur import Assistant

AIDE_IDENTIFICATION = ("Pour commencer, identifiez-vous : envoyez /client suivi de votre "
                       "identifiant, par exemple /client CLI-0002. En production, le canal ne prouve pas qui vous êtes : "
                       "une authentification réelle est nécessaire.")


@dataclass
class Message:
    """Un message entrant, quel que soit le canal."""
    canal: str
    utilisateur: str        # identifiant propre au canal (numéro WhatsApp)
    texte: str
    id: str = ""            # identifiant du message chez le canal, pour écarter les doublons


class Canal(Protocol):
    """Ce qu'un canal fournit à la passerelle : un nom et une méthode d'envoi."""
    nom: str

    async def envoyer(self, utilisateur: str, texte: str) -> None: ...


def _chiffres(numero: str) -> str:
    """Le numéro réduit à ses chiffres, sans le préfixe international « 00 » : WhatsApp envoie 22898836424 pour +228 98 83 64 24 ou 00228 98 83 64 24."""
    return re.sub(r"^0+", "", re.sub(r"\D", "", numero))


class Passerelle:
    """Relie les canaux ({nom: canal}) à l'assistant."""

    def __init__(self, assistant: Assistant, canaux: dict[str, Canal]):
        self.assistant = assistant
        self.canaux = canaux
        self.metriques = suivi.Metrics()
        self.identites: dict[tuple[str, str], str] = {}           # (canal, utilisateur) -> client_id
        self.sessions: dict[tuple[str, str], int] = defaultdict(int)   # compteur de /reset
        self.validations: dict[str, dict] = {}                     # session_id -> dossier en attente
        self.transferts: dict[str, dict] = {}                      # référence de réclamation -> dossier transmis
        self.prises: dict[tuple[str, str], str] = {}               # (canal, utilisateur) -> dossier pris par un conseiller
        self.max_par_heure = int(os.getenv("MAX_MSG_PER_HOUR") or 30)
        self.identification_par_commande = os.getenv("IDENTIFICATION_PAR_COMMANDE", "1") == "1"
        self._vus: set[str] = set()
        self._verrous: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._usage: dict[str, list[float]] = defaultdict(list)
        for numero, client in json.loads(os.getenv("IDENTITES") or "{}").items():   # ex. {"2250700000000": "CLI-0002"}
            self.identites[("whatsapp", _chiffres(numero))] = client

    # ------------------------------------------------------------ identification
    def identifier(self, msg: Message) -> Optional[str]:
        """Le client de l'expéditeur : identité connue, numéro WhatsApp d'un client, sinon CLIENT_PAR_DEFAUT (formation)."""
        cle = (msg.canal, msg.utilisateur)
        if cle in self.identites:
            return self.identites[cle]
        if msg.canal == "whatsapp":                                # le numéro d'un client Lagune Money
            with connect() as con:
                for client_id, tel in con.execute("SELECT client_id, telephone_om FROM clients"):
                    if _chiffres(tel) == _chiffres(msg.utilisateur):
                        return client_id
        return os.getenv("CLIENT_PAR_DEFAUT") or None             # formation : tout expéditeur inconnu est ce client

    def _session(self, msg: Message) -> str:
        return f"{msg.canal}:{msg.utilisateur}:{self.sessions[(msg.canal, msg.utilisateur)]}"

    def _limite(self, utilisateur: str) -> bool:
        """True si l'utilisateur a déjà envoyé MAX_MSG_PER_HOUR messages dans l'heure."""
        maintenant = time.time()
        self._usage[utilisateur] = [t for t in self._usage[utilisateur] if maintenant - t < 3600]
        if len(self._usage[utilisateur]) >= self.max_par_heure:
            return True
        self._usage[utilisateur].append(maintenant)
        return False

    # ------------------------------------------------------------ traitement d'un message
    async def traiter(self, msg: Message) -> None:
        """Traite un message entrant et envoie la réponse dans son canal."""
        if msg.id:
            if msg.id in self._vus:                                # le canal peut renvoyer un même message
                return
            self._vus.add(msg.id)
            if len(self._vus) > 5000:
                self._vus.clear()
        canal = self.canaux[msg.canal]
        if self._limite(f"{msg.canal}:{msg.utilisateur}"):
            return await canal.envoyer(msg.utilisateur, "Vous avez atteint la limite de messages pour cette heure. Réessayez plus tard.")

        texte = msg.texte.strip()
        async with self._verrous[f"{msg.canal}:{msg.utilisateur}"]:     # un seul traitement à la fois par utilisateur
            commande = re.match(r"^/(\w+)\s*(.*)$", texte)
            if commande:
                return await canal.envoyer(msg.utilisateur, self._commande(msg, commande.group(1).lower(), commande.group(2).strip()))
            client_id = self.identifier(msg)
            if client_id is None:
                if msg.canal == "whatsapp":                      # le numéro exact à copier dans IDENTITES
                    print(f"Numéro WhatsApp inconnu : {msg.utilisateur}. Pour l'identifier, ajoutez-le dans IDENTITES (.env).")
                return await canal.envoyer(msg.utilisateur, AIDE_IDENTIFICATION)
            prise = self.prises.get((msg.canal, msg.utilisateur))
            if prise:                                            # un conseiller a la main : l'assistant ne répond pas
                self.transferts[prise]["messages"].append({"de": "client", "texte": texte, "heure": time.strftime("%H:%M")})
                self.assistant.history.add(msg.utilisateur, "client", texte)
                return
            session = self._session(msg)
            if session in self.validations:
                return await canal.envoyer(msg.utilisateur, "Votre demande est en cours de validation par un conseiller. "
                                                           "Je vous écris dès qu'il a décidé.")
            deja = self._reclamations(client_id)
            try:
                rep = await asyncio.to_thread(self.assistant.reply, session, client_id, texte, msg.utilisateur)
            except Exception as e:                                 # le client ne voit jamais une trace d'erreur
                print("Erreur agent :", repr(e))
                return await canal.envoyer(msg.utilisateur, "Un incident technique m'empêche de répondre. Réessayez dans un instant "
                                                           "ou écrivez « conseiller ».")
            self.metriques.record(rep.categorie, rep.bilan, rep.transfert, rep.bloque)
            if rep.validation:
                self.validations[session] = {"session": session, "canal": msg.canal, "utilisateur": msg.utilisateur,
                                             "client_id": client_id, "dossier": rep.validation,
                                             "recu_le": time.strftime("%Y-%m-%dT%H:%M:%S")}
            for ref, dossier in self._reclamations(client_id).items():   # dossiers créés pendant ce tour : handoffs
                if ref not in deja:
                    self.transferts[ref] = {"reference": ref, "session": session, "canal": msg.canal, "utilisateur": msg.utilisateur,
                                            "client_id": client_id, "dossier": dossier, "recu_le": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                            "statut": "nouveau", "conseiller": None,
                                            "messages": [{"de": role, "texte": c, "heure": ""} for role, c in
                                                         self.assistant.history.messages(msg.utilisateur)[-6:]]}
            await canal.envoyer(msg.utilisateur, rep.texte)

    def _commande(self, msg: Message, nom: str, argument: str) -> str:
        """Commandes /start, /reset et /client : renvoie le texte à envoyer."""
        if nom == "start":
            return "Bonjour ! " + AIDE_IDENTIFICATION if self.identifier(msg) is None else "Bonjour ! Posez votre question."
        if nom == "reset":
            self.sessions[(msg.canal, msg.utilisateur)] += 1
            self.assistant.forget(msg.utilisateur)
            return "C'est fait : nouvelle conversation."
        if nom == "client":
            if not self.identification_par_commande:
                return "L'identification par commande est désactivée."
            with connect() as con:
                existe = con.execute("SELECT 1 FROM clients WHERE client_id = ?", (argument.upper(),)).fetchone()
            if not existe:
                return "Identifiant inconnu. Format attendu : CLI-0002."
            self.identites[(msg.canal, msg.utilisateur)] = argument.upper()
            return f"Identifié : {argument.upper()} . Que puis-je faire pour vous ?"
        return "Commande inconnue."

    # ------------------------------------------------------------ côté conseiller
    def _reclamations(self, client_id: str) -> dict[str, dict]:
        """Les réclamations du client dans la base : référence -> dossier."""
        with connect() as con:
            lignes = con.execute("SELECT reclamation_id, dossier_json FROM reclamations WHERE client_id = ?", (client_id,)).fetchall()
        return {ref: json.loads(d) for ref, d in lignes}

    def transferts_en_cours(self) -> list[dict]:
        """Les dossiers transmis par l'assistant : nouveaux, ou pris en charge par un conseiller."""
        return list(self.transferts.values())

    def _dossier(self, reference: str) -> dict:
        if reference not in self.transferts:
            raise LookupError("Aucun dossier transmis avec cette référence.")
        return self.transferts[reference]

    async def _ecrire(self, dossier: dict, texte: str) -> None:
        """Message du conseiller : envoyé dans le canal, gardé dans le dossier et dans la mémoire de la conversation."""
        await self.canaux[dossier["canal"]].envoyer(dossier["utilisateur"], texte)
        self.assistant.history.add(dossier["utilisateur"], "assistant", texte)
        dossier["messages"].append({"de": "conseiller", "texte": texte, "heure": time.strftime("%H:%M")})

    async def prendre_en_charge(self, reference: str, conseiller: str) -> str:
        """Le conseiller prend la main : l'assistant se tait et les messages du client lui arrivent."""
        dossier = self._dossier(reference)
        dossier["statut"], dossier["conseiller"] = "en_cours", conseiller
        self.prises[(dossier["canal"], dossier["utilisateur"])] = reference
        with connect() as con:
            con.execute("UPDATE reclamations SET statut = 'en_cours' WHERE reclamation_id = ?", (reference,))
        texte = f"Un conseiller de Lagune Banque prend la suite de votre demande (dossier {reference}). Vous pouvez lui écrire ici."
        await self._ecrire(dossier, texte)
        return texte

    async def message_conseiller(self, reference: str, texte: str) -> None:
        """Un message écrit par le conseiller, envoyé au client."""
        dossier = self._dossier(reference)
        if dossier["statut"] != "en_cours":
            raise LookupError("Prenez d'abord le dossier en charge.")
        await self._ecrire(dossier, texte)

    async def clore(self, reference: str) -> str:
        """Le conseiller termine l'échange : le dossier est clos et l'assistant reprend la conversation."""
        dossier = self._dossier(reference)
        texte = "Votre échange avec le conseiller est terminé. L'assistant de Lagune Banque reste à votre disposition ici."
        await self._ecrire(dossier, texte)
        self.prises.pop((dossier["canal"], dossier["utilisateur"]), None)
        del self.transferts[reference]
        with connect() as con:
            con.execute("UPDATE reclamations SET statut = 'close' WHERE reclamation_id = ?", (reference,))
        return texte

    def en_attente(self) -> list[dict]:
        """Les dossiers en attente de la décision d'un conseiller."""
        return list(self.validations.values())

    async def decide(self, session: str, approuve: bool, conseiller: str, motif: str = "") -> str:
        """Le conseiller décide : l'agent reprend, et le client reçoit la suite dans son canal."""
        attente = self.validations.get(session)
        if attente is None:
            raise LookupError("Aucune validation en attente pour cette session.")
        rep = await asyncio.to_thread(self.assistant.decide, session, attente["client_id"], approuve, conseiller, motif)
        del self.validations[session]
        self.metriques.record(rep.categorie, rep.bilan, False, rep.bloque)
        await self.canaux[attente["canal"]].envoyer(attente["utilisateur"], rep.texte)
        return rep.texte
