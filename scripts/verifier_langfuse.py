"""Vérifie la connexion à Langfuse Cloud (LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST dans .env).

À lancer depuis la racine du dépôt : uv run python scripts/verifier_langfuse.py
Compte Hobby gratuit (50 000 unités par mois, sans carte bancaire) sur https://cloud.langfuse.com. LANGFUSE_HOST doit être la région du
projet : https://cloud.langfuse.com (Europe) ou https://us.cloud.langfuse.com (États-Unis).
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def echec(message: str) -> None:
    print(f"ÉCHEC : {message}")
    sys.exit(1)


if not (os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")):
    echec("LANGFUSE_PUBLIC_KEY et LANGFUSE_SECRET_KEY ne sont pas renseignés (Settings > API Keys dans Langfuse Cloud).")
os.environ.setdefault("LANGFUSE_HOST", "https://cloud.langfuse.com")

from langfuse import Langfuse

try:
    ok = Langfuse().auth_check()
except Exception as e:
    echec(f"Langfuse est injoignable ({type(e).__name__}). Vérifiez le réseau et LANGFUSE_HOST.")
if not ok:
    echec(f"clés refusées sur {os.environ['LANGFUSE_HOST']}. Les clés d'un projet américain ne marchent que sur "
          "https://us.cloud.langfuse.com : vérifiez la région et LANGFUSE_HOST.")
print(f"OK : connecté à Langfuse ({os.environ['LANGFUSE_HOST']}).")
