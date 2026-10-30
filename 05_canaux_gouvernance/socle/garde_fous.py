"""Garde-fous de l'assistant : filtrage de l'entrée et de la sortie, masquage des données personnelles.

Un guardrail ne modifie pas le modèle : il s'exécute avant l'appel (entrée) et avant l'envoi au client (sortie).
Règles simples, volontairement lisibles : en production, on les complète par NeMo Guardrails, Guardrails AI
ou la modération du fournisseur.
"""
import re
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(next(p / "code_partage" for p in Path(__file__).resolve().parents if (p / "code_partage" / "observabilite.py").exists())))
from observabilite import mask, mask_data  # noqa: E402,F401  (le masquage sert aussi aux traces Langfuse des modules 2 et 3)

ANNONCE_IA = "Bonjour, je suis l'assistant virtuel de Lagune Banque. Vous pouvez demander un conseiller à tout moment."

REFUS_CREDIT = ("Je ne peux pas prendre de décision de crédit (octroi, plafond, rééchelonnement). "
                "Un conseiller peut étudier votre demande : écrivez « conseiller » et je vous mets en relation.")

TRANSFERT = "Je vous mets en relation avec un conseiller. Votre dossier lui est transmis : vous n'aurez pas à tout répéter."

# LLM06 (Excessive Agency) : l'assistant ne décide pas d'un crédit, ni en entrée ni en sortie.
CREDIT_ENTREE = [
    r"accord(?:ez|er)\b.{0,40}\b(pr[eê]t|cr[eé]dit)",
    r"augment(?:ez|er)\b.{0,40}\bplafond", r"\bplafond\b.{0,40}\baugment",
    r"octro(?:yez|yer)", r"r[eé][ée]chelonn",
    r"(puis-je|pouvez-vous|peut-on)\b.{0,30}\b(avoir|obtenir|accorder)\b.{0,30}\b(pr[eê]t|cr[eé]dit)",
]
CREDIT_SORTIE = [
    r"je vous accorde", r"nous vous accordons", r"pr[eê]t (?:est |a été )?(?:accord[ée]|approuv[ée]|octroy[ée])",
    r"vous [êe]tes [ée]ligible", r"j'ai (?:augment[ée]|relev[ée])", r"votre plafond (?:sera|est port[ée])",
]
DEMANDE_CONSEILLER = r"(parler|passer|transf[ée]rer?|mettre|joindre)\b.{0,30}\b(conseiller|humain|quelqu'un)|\bconseiller\b\s*$|^\s*conseiller\b"


def check_input(texte: str) -> Optional[str]:
    """Renvoie la réponse de refus si le message demande une décision de crédit, sinon None."""
    if any(re.search(m, texte, re.I) for m in CREDIT_ENTREE):
        return REFUS_CREDIT
    return None


def strip_references(texte: str) -> str:
    """Retire les références de documents (« [DOC-01, DOC-03] ») : le client n'a pas à les voir."""
    texte = re.sub(r"\s*\[\s*DOC-[^\]]*\]", "", texte)
    texte = re.sub(r"\s*\(\s*DOC-\d+[^)]*\)", "", texte)
    texte = re.sub(r"\(\s*[,;\s]*\)", "", texte)
    texte = re.sub(r"[ \t]+([.,;])", r"\1", texte)
    return re.sub(r"[ \t]{2,}", " ", texte).strip()


def check_output(texte: str) -> str:
    """Retire les références de documents, et remplace toute réponse assimilable à une décision de crédit (LLM05 : sortie non maîtrisée)."""
    texte = strip_references(texte)
    if any(re.search(m, texte, re.I) for m in CREDIT_SORTIE):
        return REFUS_CREDIT
    return texte


def asks_for_advisor(texte: str) -> bool:
    return bool(re.search(DEMANDE_CONSEILLER, texte, re.I))
