"""Historique des conversations : une base SQLite locale, une conversation par expéditeur.

La clé est l'identifiant de l'expéditeur sur le canal : le numéro de téléphone WhatsApp. L'historique
survit donc au redémarrage du service, et l'assistant garde le fil d'une conversation d'un jour à l'autre.

Quand la conversation devient trop longue, les anciens messages sont résumés (`compact`) : le résumé et les derniers
messages restent seuls dans le contexte envoyé au modèle.
"""
import sqlite3
import threading
from typing import Callable


class History:
    """Messages et résumés des conversations, rangés par clé (l'expéditeur)."""

    def __init__(self, chemin: str = ":memory:"):
        """`chemin` : fichier SQLite (créé au besoin). Par défaut, une base en mémoire : l'historique ne survit pas au processus."""
        self._con = sqlite3.connect(chemin, check_same_thread=False)
        self._verrou = threading.Lock()                       # le service appelle l'assistant depuis plusieurs threads
        with self._verrou, self._con:
            self._con.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, cle TEXT NOT NULL, "
                              "role TEXT NOT NULL, contenu TEXT NOT NULL, date TEXT DEFAULT CURRENT_TIMESTAMP)")
            self._con.execute("CREATE INDEX IF NOT EXISTS idx_messages_cle ON messages(cle, id)")
            self._con.execute("CREATE TABLE IF NOT EXISTS resumes (cle TEXT PRIMARY KEY, texte TEXT NOT NULL)")

    def add(self, cle: str, role: str, contenu: str) -> None:
        """`role` : « client » ou « assistant »."""
        with self._verrou, self._con:
            self._con.execute("INSERT INTO messages (cle, role, contenu) VALUES (?, ?, ?)", (cle, role, contenu))

    def messages(self, cle: str) -> list[tuple[str, str]]:
        """Les messages conservés, du plus ancien au plus récent : [(role, contenu)]."""
        with self._verrou:
            return self._con.execute("SELECT role, contenu FROM messages WHERE cle = ? ORDER BY id", (cle,)).fetchall()

    def summary(self, cle: str) -> str:
        """Le résumé des anciens messages, ou une chaîne vide."""
        with self._verrou:
            ligne = self._con.execute("SELECT texte FROM resumes WHERE cle = ?", (cle,)).fetchone()
        return ligne[0] if ligne else ""

    def volume(self, cle: str) -> int:
        """Nombre de caractères conservés pour cette conversation (messages et résumé)."""
        with self._verrou:
            n = self._con.execute("SELECT COALESCE(SUM(LENGTH(contenu)), 0) FROM messages WHERE cle = ?", (cle,)).fetchone()[0]
        return n + len(self.summary(cle))

    def compact(self, cle: str, seuil: int, garder: int, resumer: Callable[[str], str]) -> bool:
        """Si la conversation dépasse `seuil` caractères, résume tout sauf les `garder` derniers messages. Renvoie True si elle a été compactée.
        `resumer(transcription)` renvoie le résumé : le résumé précédent est inclus dans la transcription."""
        if self.volume(cle) <= seuil:
            return False
        with self._verrou:
            lignes = self._con.execute("SELECT id, role, contenu FROM messages WHERE cle = ? ORDER BY id", (cle,)).fetchall()
        anciens = lignes[:-garder] if garder else lignes
        if not anciens:
            return False
        precedent = self.summary(cle)
        transcription = (f"Résumé précédent : {precedent}\n" if precedent else "") + "\n".join(f"{r} : {c}" for _, r, c in anciens)
        nouveau = resumer(transcription).strip()
        with self._verrou, self._con:
            self._con.execute("INSERT INTO resumes (cle, texte) VALUES (?, ?) ON CONFLICT(cle) DO UPDATE SET texte = excluded.texte",
                              (cle, nouveau))
            self._con.executemany("DELETE FROM messages WHERE id = ?", [(i,) for i, _, _ in anciens])
        return True

    def clear(self, cle: str) -> None:
        """Oublie la conversation (commande /reset)."""
        with self._verrou, self._con:
            self._con.execute("DELETE FROM messages WHERE cle = ?", (cle,))
            self._con.execute("DELETE FROM resumes WHERE cle = ?", (cle,))
