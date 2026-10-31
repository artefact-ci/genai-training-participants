"""Configuration commune des notebooks : charge .env et vérifie la connexion aux modèles."""
import logging
import os
import warnings
from pathlib import Path

import litellm
from dotenv import load_dotenv


def prepare(embedding: bool = False, rerank: bool = False) -> None:
    """Charge `.env`, puis teste le modèle de chat, et si demandé le modèle d'embedding et le reranker. Échoue avec un message clair."""
    logging.getLogger("LiteLLM").setLevel(logging.CRITICAL)                 # moins de bruit dans les sorties des notebooks
    litellm.suppress_debug_info = True
    warnings.filterwarnings("ignore", message="IProgress not found")
    for dossier in [Path.cwd(), *Path.cwd().parents]:
        if (dossier / ".env").exists():
            load_dotenv(dossier / ".env")
            break
    litellm.drop_params = True                                              # ignore les paramètres qu'un fournisseur ne connaît pas
    requises = ["LLM_API_KEY", "MODELE"] + (["MODELE_EMBEDDING"] if embedding else []) + (["MODELE_RERANK", "RERANK_API_KEY"] if rerank else [])
    manquantes = [v for v in requises if not os.getenv(v)]
    if manquantes:
        raise RuntimeError(f"Renseignez {', '.join(manquantes)} dans .env.")
    cle = os.environ["LLM_API_KEY"]
    try:
        litellm.completion(model=os.environ["MODELE"], api_key=cle, max_tokens=20, messages=[{"role": "user", "content": "Réponds : OK"}])
        if embedding:
            litellm.embedding(model=os.environ["MODELE_EMBEDDING"], input=["test"], api_key=cle)
        if rerank:
            base = {"api_base": os.environ["RERANK_API_BASE"]} if os.getenv("RERANK_API_BASE") else {}
            litellm.rerank(model=os.environ["MODELE_RERANK"], query="test", documents=["test"], top_n=1, api_key=os.environ["RERANK_API_KEY"], **base)
    except Exception as e:
        raise RuntimeError(f"Connexion impossible ({type(e).__name__}). Vérifiez les modèles et les clés dans .env.") from None
    print("Connexion OK :", os.environ["MODELE"], *([os.environ["MODELE_EMBEDDING"]] if embedding else []), *([os.environ["MODELE_RERANK"]] if rerank else []))
