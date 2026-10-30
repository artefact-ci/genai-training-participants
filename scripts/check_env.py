"""Vérifie que l'environnement est prêt : fichier .env, clé API et appel au modèle."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

RACINE = Path(__file__).resolve().parent.parent


def echec(message: str) -> None:
    print(f"ÉCHEC : {message}")
    sys.exit(1)


def main() -> None:
    load_dotenv(RACINE / ".env")

    manquantes = [v for v in ("LLM_API_KEY", "MODELE") if not os.getenv(v, "").strip()]
    if manquantes:
        echec(
            f"variable(s) non renseignée(s) : {', '.join(manquantes)}. "
            "Copiez .env.example en .env puis complétez-le."
        )

    import litellm

    try:
        reponse = litellm.completion(
            model=os.environ["MODELE"],
            api_key=os.environ["LLM_API_KEY"],
            messages=[{"role": "user", "content": "Réponds en une phrase : bonjour !"}],
            max_tokens=50,
        )
    except litellm.AuthenticationError:
        echec("clé API refusée. Vérifiez LLM_API_KEY dans le fichier .env.")
    except litellm.NotFoundError:
        echec("modèle introuvable. Vérifiez la valeur de MODELE dans le fichier .env.")
    except litellm.BadRequestError:
        echec("requête invalide. Vérifiez le format de MODELE (ex. fournisseur/nom-du-modèle).")
    except (litellm.APIConnectionError, litellm.Timeout):
        echec("impossible de joindre le fournisseur. Vérifiez votre connexion réseau.")
    except Exception as e:
        echec(f"appel au modèle impossible ({type(e).__name__}).")

    texte = (reponse.choices[0].message.content or "").strip()
    print(f"OK : le modèle {os.environ['MODELE']} répond : {texte}")

    modele_embedding = os.getenv("MODELE_EMBEDDING", "").strip()
    if not modele_embedding:
        echec("MODELE_EMBEDDING n'est pas renseigné (modèle d'embedding du module 2, par exemple text-embedding-3-small).")
    try:
        litellm.embedding(model=modele_embedding, input=["bonjour"], api_key=os.environ["LLM_API_KEY"])
    except Exception as e:
        echec(f"appel au modèle d'embedding impossible ({type(e).__name__}). Vérifiez MODELE_EMBEDDING dans le fichier .env.")
    print(f"OK : le modèle d'embedding {modele_embedding} répond.")

    modele_rerank = os.getenv("MODELE_RERANK", "").strip()
    if not modele_rerank:
        print("Reranker non configuré (MODELE_RERANK vide) : il n'est nécessaire que pour le TP « recherche hybride et reranking » du module 2.")
        return
    try:
        base = {"api_base": os.environ["RERANK_API_BASE"]} if os.getenv("RERANK_API_BASE") else {}
        litellm.rerank(model=modele_rerank, query="bonjour", documents=["bonjour", "au revoir"], top_n=1, api_key=os.getenv("RERANK_API_KEY", ""), **base)
    except Exception as e:
        echec(f"appel au reranker impossible ({type(e).__name__}). Vérifiez MODELE_RERANK, RERANK_API_KEY et RERANK_API_BASE dans le fichier .env.")
    print(f"OK : le reranker {modele_rerank} répond.")


if __name__ == "__main__":
    main()
