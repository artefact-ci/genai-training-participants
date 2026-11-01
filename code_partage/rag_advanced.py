"""RAG avancé : réécriture de la question, variantes, HyDE, BM25, mesure de la recherche, sortie structurée et réponse sourcée.

Versions de référence de fonctions construites au module 2, réutilisées par les notebooks suivants.
"""
import json
import math
import os
import re
import time
import unicodedata
from pathlib import Path
from typing import Callable, Optional

import litellm
import rag
from pydantic import BaseModel

APPELS = {"llm": 0}                       # nombre d'appels au modèle, pour comparer le coût des méthodes


def normalize(texte: str) -> str:
    """Le texte sans différences de casse ni d'espaces, pour comparer deux extraits."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", texte)).casefold()


def _strip_accents(texte: str) -> str:
    """Le texte en minuscules et sans accents (pour BM25)."""
    return "".join(c for c in unicodedata.normalize("NFD", texte.casefold()) if unicodedata.category(c) != "Mn")


def _llm(prompt: str) -> str:
    """Réponse du modèle (MODELE) via LiteLLM ; l'appel est compté dans APPELS."""
    APPELS["llm"] += 1
    r = litellm.completion(model=os.environ["MODELE"], api_key=os.environ["LLM_API_KEY"], temperature=0, max_tokens=300, num_retries=4,
                           messages=[{"role": "user", "content": prompt}])
    return (r.choices[0].message.content or "").strip()


def rewrite(question: str, echange: str = "", mots_cles: bool = False) -> str:
    """La question réécrite en requête de recherche autonome. `echange` : les messages précédents, pour les questions de suite (« Et pour l'Express+ ? »).
    Par défaut la réécriture reste fidèle (fautes corrigées, renvois résolus, rien d'ajouté). Avec `mots_cles`, elle ajoute des synonymes et des termes de métier."""
    contexte = f"Échange précédent :\n{echange}\n" if echange else ""
    if mots_cles:
        return _llm("Réécris la dernière question d'un client de banque en une requête de recherche autonome et précise : mots-clés utiles, synonymes, "
                    f"en français, sans politesse. Réponds uniquement par la requête.\n{contexte}Question : {question}")
    return _llm("Réécris la dernière question du client pour qu'elle soit compréhensible seule : remplace les renvois à l'échange précédent et corrige les fautes. "
                "Ne change rien d'autre, n'ajoute aucun mot. Si la question est déjà claire, renvoie-la telle quelle. "
                f"Réponds uniquement par la question.\n{contexte}Question : {question}")


def variants(question: str, n: int = 3) -> list[str]:
    """`n` reformulations de la question."""
    texte = _llm(f"Écris {n} reformulations différentes de cette question d'un client de banque, une par ligne, sans numéro ni commentaire.\nQuestion : {question}")
    return [ligne.strip("-• ").strip() for ligne in texte.splitlines() if ligne.strip()][:n]


def hypothesis(question: str) -> str:
    """HyDE : une réponse imaginée à la question. On cherche avec elle, car une réponse ressemble plus au chunk cherché qu'une question."""
    return _llm("Écris en deux phrases la réponse que donnerait la documentation d'une banque à cette question, même si tu dois inventer les chiffres.\n"
                f"Question : {question}")


class BM25:
    """Recherche par mots-clés : un chunk score d'autant plus qu'il contient les mots rares de la question."""

    def __init__(self, chunks: list[dict], k1: float = 1.5, b: float = 0.75):
        self.chunks, self.k1, self.b = chunks, k1, b
        self.mots = [self._words(p["texte"]) for p in chunks]
        self.moyenne = sum(map(len, self.mots)) / len(self.mots)
        self.frequence = {}
        for mots in self.mots:
            for m in set(mots):
                self.frequence[m] = self.frequence.get(m, 0) + 1

    @staticmethod
    def _words(texte: str) -> list[str]:
        return re.findall(r"\w+", _strip_accents(texte))

    def search(self, question: str, n: int = 10) -> list[dict]:
        """Les `n` chunks au meilleur score, sans ceux qui ne partagent aucun mot avec la question."""
        scores = []
        for i, mots in enumerate(self.mots):
            score = 0.0
            for m in set(self._words(question)):
                f = mots.count(m)
                if f:
                    rarete = math.log(1 + (len(self.mots) - self.frequence[m] + 0.5) / (self.frequence[m] + 0.5))
                    score += rarete * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * len(mots) / self.moyenne))
            scores.append((score, i))
        return [self.chunks[i] for s, i in sorted(scores, reverse=True)[:n] if s > 0]


def load_questions(nom: Optional[str] = None) -> dict | list[dict]:
    """Les questions de référence (`data/evaluation/questions_rag.json`) : le jeu `representatif`, le jeu `difficile`, ou les deux."""
    dossier = next(p / "data" / "evaluation" for p in Path(__file__).resolve().parents if (p / "data" / "evaluation" / "questions_rag.json").exists())
    jeux = json.loads((dossier / "questions_rag.json").read_text(encoding="utf-8"))
    return jeux[nom] if nom else jeux


def rank(chunks: list[dict], elements: list[str]) -> Optional[int]:
    """Le rang du premier chunk qui contient tous les éléments de la réponse, ou None."""
    for i, p in enumerate(chunks, 1):
        if all(e in normalize(p["texte"]) for e in elements):
            return i
    return None


def measure(recherche: Callable[[str, str], list[dict]], jeu: list[dict]) -> dict:
    """Applique `recherche(question, echange)` à chaque question du jeu. Renvoie le MRR, le nombre de bons chunks en première position, dans les 3 premiers,
    le nombre d'absents (hors des 10 premiers), le temps et le nombre d'appels au modèle par question."""
    rangs, debut, appels = [], time.time(), APPELS["llm"]
    for x in jeu:
        rangs.append(rank(recherche(x["question"], x["historique"]), x["elements"]))
    n = len(jeu)
    return {"MRR": round(sum(1 / r for r in rangs if r) / n, 2), "en 1er": sum(r == 1 for r in rangs), "dans les 3 premiers": sum(bool(r and r <= 3) for r in rangs),
            "absents": sum(r is None for r in rangs), "secondes": round((time.time() - debut) / n, 2), "appels LLM": round((APPELS["llm"] - appels) / n, 1), "rangs": rangs}


# ------------------------------------------------------------------ génération sous contrôle (TP3) et jugement (TP4)
def structured(prompt: str, schema):
    """Réponse du modèle (MODELE) validée par un schéma Pydantic (sortie structurée). Renvoie None si le modèle ne respecte pas le schéma."""
    APPELS["llm"] += 1
    r = litellm.completion(model=os.environ["MODELE"], api_key=os.environ["LLM_API_KEY"], temperature=0, max_tokens=900, num_retries=4,
                           response_format=schema, messages=[{"role": "user", "content": prompt}])
    try:
        return schema.model_validate_json(r.choices[0].message.content or "")
    except ValueError:
        return None


# Schéma de la réponse sourcée (TP3)
class Citation(BaseModel):
    source: str
    extrait: str


class SourcedAnswer(BaseModel):
    reponse: str
    citations: list[Citation]


# Prompt par défaut de `answer_with_sources` : un notebook peut passer le sien.
PROMPT_SOURCES = """Tu es l'assistant du service client de Lagune Banque.
Réponds UNIQUEMENT à partir des chunks fournis, en 2 à 4 phrases. N'invente aucun chiffre, délai ou condition.
Si l'information n'y figure pas, mets "reponse" à "REFUS" et laisse "citations" vide.
Pour chaque citation, "source" est l'identifiant seul (DOC-xx, sans la version) et "extrait" un texte copié mot pour mot depuis le chunk.

# Chunks
{chunks}

# Question
{question}
"""


def verify_citations(citations: list[dict], chunks: list[dict]) -> list[dict]:
    """Les citations dont l'extrait figure, mot pour mot, dans un chunk de la même source."""
    return [c for c in citations
            if any(p["meta"]["source"] == c.get("source") and normalize(c.get("extrait", "")) in normalize(p["texte"]) for p in chunks)]


def answer_with_sources(question: str, chunks: list[dict], seuil: float = 0.64, prompt: str = PROMPT_SOURCES) -> dict:
    """Réponse sous contrôle : refus si le meilleur score de reranker est sous `seuil`, sinon réponse structurée dont les citations sont vérifiées.
    Une réponse sans aucune citation vérifiée est un refus. `prompt` contient `{chunks}` et `{question}`."""
    refus = {"reponse": rag.REFUS, "refus": True, "citations": [], "chunks": chunks}
    if not chunks or chunks[0]["score"] < seuil:
        return refus
    sortie = structured(prompt.format(chunks=rag.format_chunks(chunks), question=question), SourcedAnswer)
    citations = verify_citations([c.model_dump() for c in sortie.citations], chunks) if sortie else []
    if not sortie or sortie.reponse.strip() == "REFUS" or not citations:
        return refus
    return {"reponse": sortie.reponse, "refus": False, "citations": citations, "chunks": chunks}
