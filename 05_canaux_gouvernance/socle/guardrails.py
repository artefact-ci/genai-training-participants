"""Garde-fous de l'assistant : filtrage de l'entrée et de la sortie, masquage des données personnelles.

Un guardrail ne modifie pas le modèle : il s'exécute avant l'appel (entrée) et avant l'envoi au client (sortie).
Règles simples, volontairement lisibles : en production, on les complète par NeMo Guardrails, Guardrails AI
ou la modération du fournisseur.
"""
import re
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(next(p / "code_partage" for p in Path(__file__).resolve().parents if (p / "code_partage" / "observability.py").exists())))
from observability import mask  # noqa: E402,F401  (masquage des données personnelles, commun avec les traces Langfuse)

AI_NOTICE = "Bonjour, je suis l'assistant virtuel de Lagune Banque. Vous pouvez demander un conseiller à tout moment."

CREDIT_REFUSAL = ("Je ne peux pas prendre de décision de crédit (octroi, plafond, rééchelonnement). "
                  "Un conseiller peut étudier votre demande : écrivez « conseiller » et je vous mets en relation.")

TRANSFER_TEXT = "Je transmets votre demande à un conseiller. Il vous répond ici dès qu'il la prend en charge."

# LLM06 (Excessive Agency) : l'assistant ne décide pas d'un crédit, ni en entrée ni en sortie.
CREDIT_INPUT = [
    r"accord(?:ez|er)\b.{0,40}\b(pr[eê]t|cr[eé]dit)",
    r"augment(?:ez|er)\b.{0,40}\bplafond", r"\bplafond\b.{0,40}\baugment",
    r"octro(?:yez|yer)", r"r[eé][ée]chelonn",
    r"(puis-je|pouvez-vous|peut-on)\b.{0,30}\b(avoir|obtenir|accorder)\b.{0,30}\b(pr[eê]t|cr[eé]dit)",
]
CREDIT_OUTPUT = [
    r"je vous accorde", r"nous vous accordons", r"pr[eê]t (?:est |a été )?(?:accord[ée]|approuv[ée]|octroy[ée])",
    r"vous [êe]tes [ée]ligible", r"j'ai (?:augment[ée]|relev[ée])", r"votre plafond (?:sera|est port[ée])",
]
# l'assistant annonce un transfert : un dossier doit alors exister pour le conseiller (contrôle de cohérence de la sortie)
TRANSFER_ANNOUNCEMENT = r"\b(je vous (mets|transf[eè]re)|je transmets)\b.{0,40}\bconseiller"


def check_input(texte: str) -> Optional[str]:
    """Renvoie la réponse de refus si le message demande une décision de crédit, sinon None."""
    if any(re.search(m, texte, re.I) for m in CREDIT_INPUT):
        return CREDIT_REFUSAL
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
    if any(re.search(m, texte, re.I) for m in CREDIT_OUTPUT):
        return CREDIT_REFUSAL
    return texte


def announces_transfer(texte: str) -> bool:
    """True si la réponse de l'assistant annonce une mise en relation avec un conseiller."""
    return bool(re.search(TRANSFER_ANNOUNCEMENT, texte, re.I))
