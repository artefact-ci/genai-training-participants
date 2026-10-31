"""Recherche dans la documentation pour `search_docs` (modules 3, 4 et 5) : l'index RAG du module 2.

Les documents de `data/corpus/` sont chargés, nettoyés et découpés par `rag.py`, puis indexés avec le modèle
d'embedding (MODELE_EMBEDDING). L'index est construit au premier appel. Avec Weaviate, il est conservé d'un lancement
à l'autre ; sans Weaviate, il est reconstruit en mémoire à chaque lancement (quelques secondes).
"""
import atexit

import rag
from weaviate_store import connect

CHUNK_SIZE, OVERLAP = 500, 75       # le découpage retenu au TP1 du module 2
COLLECTION = "docs_agents"
_index = None


def _build():
    """Charge, nettoie, découpe et indexe le corpus (index réutilisé s'il existe déjà dans Weaviate)."""
    documents = rag.load_corpus()
    for d in documents:
        if d["fichier"].endswith(".pdf") and not d["avertissement"]:       # l'en-tête répété de chaque page (pas dans la transcription du scan)
            d["pages"] = rag.strip_headers(d["pages"])
    client = connect()
    atexit.register(client.close)
    return rag.index_chunks(client, COLLECTION, rag.split_documents(documents, CHUNK_SIZE, OVERLAP, "agents"), reutiliser=True)


def find_docs(question: str, date: str, k: int = 3) -> list[dict]:
    """Les k chunks les plus proches parmi les documents en vigueur à `date` (AAAA-MM-JJ) : [{source, titre, version, extrait}]."""
    global _index
    if _index is None:
        _index = _build()
    return [{"source": p["meta"]["source"], "titre": p["meta"]["titre"], "version": p["meta"]["version"], "extrait": p["texte"]}
            for p in rag.search(_index, question, k, date)]
