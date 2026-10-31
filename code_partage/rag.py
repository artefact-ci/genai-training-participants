"""Briques du RAG : charger, nettoyer, découper, calculer les embeddings, rechercher, reclasser, générer.

Utilisé par les TP du module 2, et par `doc_search.py` pour l'outil `search_docs` des modules 3, 4 et 5.
Les modèles sont appelés via LiteLLM : pour changer de fournisseur, modifiez MODELE et MODELE_EMBEDDING dans .env.
Inspiré du TP de chunking de souleymanecoulibaly-stack (branche tp-rag-lagune-bank).
"""
import json
import os
import re
import time
from pathlib import Path
from typing import Optional


def _data_dir() -> Path:
    """Le dossier `data/` de la formation (corpus/ et banque.db)."""
    return next(p / "data" for p in Path(__file__).resolve().parents if (p / "data" / "corpus" / "manifest.json").exists())


DATA = _data_dir()
CORPUS = DATA / "corpus"
AUJOURDHUI = "2026-11-16"                                                  # date de référence des TP
REFUS = "Je ne trouve pas cette information dans la documentation fournie."


# ------------------------------------------------------------------ chargement
# Lecture d'un fichier selon son format : une liste de (numéro de page, texte).
def _read_pdf(chemin):
    from pypdf import PdfReader
    return [(i + 1, p.extract_text() or "") for i, p in enumerate(PdfReader(chemin).pages)]


def _read_html(chemin):
    from bs4 import BeautifulSoup
    soupe = BeautifulSoup(Path(chemin).read_text(encoding="utf-8"), "html.parser")
    for balise in soupe(["script", "style"]):
        balise.decompose()
    return [(1, re.sub(r"\n\s*\n+", "\n\n", soupe.get_text("\n")).strip())]


def _read_docx(chemin):
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    doc, blocs = Document(chemin), []
    for el in doc.element.body.iterchildren():                          # paragraphes et tableaux, dans l'ordre du document
        if el.tag.endswith("}p"):
            blocs.append(Paragraph(el, doc).text)
        elif el.tag.endswith("}tbl"):
            blocs += [" | ".join(c.text.strip() for c in ligne.cells) for ligne in Table(el, doc).rows]
    return [(1, "\n".join(b for b in blocs if b.strip()))]


def load_corpus(dossier: Path = CORPUS) -> list[dict]:
    """Les documents du manifeste, un dict par document : métadonnées, `pages` [(numéro, texte)] et `avertissement`.

    Une note scannée n'a pas de texte à extraire : on utilise alors sa transcription `<nom>.ocr.txt`, et on le signale."""
    documents = []
    for m in json.loads((Path(dossier) / "manifest.json").read_text(encoding="utf-8")):
        chemin = Path(dossier) / m["fichier"]
        pages = {".pdf": _read_pdf, ".html": _read_html, ".docx": _read_docx}[chemin.suffix](chemin)
        avertissement = ""
        if not any(t.strip() for _, t in pages):
            ocr = chemin.with_suffix(".ocr.txt")
            if ocr.exists():
                pages, avertissement = [(1, ocr.read_text(encoding="utf-8"))], "scanné : aucun texte extrait, transcription OCR utilisée"
            else:
                avertissement = "scanné : aucun texte extrait (OCR nécessaire), document ignoré"
        documents.append({**m, "pages": pages, "avertissement": avertissement})
    return documents


def strip_headers(pages: list[tuple[int, str]], nb_lignes: int = 3) -> list[tuple[int, str]]:
    """Retire l'en-tête répété en haut de chaque page d'un PDF (ex. « DOC-01 · ... / En vigueur depuis... / Page 3 »).
    Sinon, chaque chunk commence par le même bruit, qui rapproche à tort tous les chunks de toutes les questions."""
    return [(n, "\n".join(t.splitlines()[nb_lignes:])) for n, t in pages]


# ------------------------------------------------------------------ chunking
def split_documents(documents: list[dict], chunk_size: int, overlap: int, nom: str = "") -> list[dict]:
    """Un dict par chunk : id, texte et métadonnées (source, titre, version, dates, page).
    Le même découpage récursif pour toutes les tailles : seuls `chunk_size` et `overlap` varient d'un essai à l'autre."""
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=overlap, separators=["\n\n", "\n", ". ", " ", ""])
    chunks = []
    for d in documents:
        for page, texte in d["pages"]:
            for i, chunk in enumerate(splitter.split_text(texte)):
                chunks.append({"id": f"{nom}_{d['id']}_p{page}_{i}", "texte": chunk,
                                 "meta": {"source": d["id"], "titre": d["titre"], "version": d["version"],
                                          "date_effet": d["date_effet"] or "", "date_fin": d["date_fin"] or "", "page": str(page)}})
    return chunks


# ------------------------------------------------------------------ embeddings
def _require(*variables: str) -> None:
    """Échoue avec un message clair si une variable manque dans .env."""
    manquantes = [v for v in variables if not os.getenv(v)]
    if manquantes:
        raise RuntimeError(f"Variable(s) manquante(s) dans .env : {', '.join(manquantes)}.")


def embeddings(textes: list[str]) -> list[list[float]]:
    """Un vecteur par texte, calculé par le modèle d'embedding (MODELE_EMBEDDING) via LiteLLM, par lots de 64."""
    _require("MODELE_EMBEDDING", "LLM_API_KEY")
    import litellm
    sortie = []
    for i in range(0, len(textes), 64):
        r = litellm.embedding(model=os.environ["MODELE_EMBEDDING"], input=textes[i:i + 64], api_key=os.environ["LLM_API_KEY"], num_retries=4)
        sortie += [d["embedding"] for d in r["data"]]
    return sortie


def index_chunks(client, nom: str, chunks: list[dict], reutiliser: bool = False):
    """Une collection vectorielle par jeu de chunks (recréée si elle existe, sauf `reutiliser=True` et une collection Weaviate non vide)."""
    from weaviate_store import create_collection
    col = create_collection(client, nom, reutiliser)
    if col.reutilisee:
        return col
    col.add([p["id"] for p in chunks], embeddings([p["texte"] for p in chunks]), [p["texte"] for p in chunks], [p["meta"] for p in chunks])
    return col


# ------------------------------------------------------------------ recherche
def is_in_force(meta: dict, date: str) -> bool:
    """Le chunk vient-il d'un document en vigueur à cette date ? Dates au format AAAA-MM-JJ : la comparaison de texte suffit."""
    return meta["date_effet"] <= date and (not meta["date_fin"] or date <= meta["date_fin"])


def search(collection, question: str, k: int = 2, date: Optional[str] = None) -> list[dict]:
    """Les k chunks les plus proches : [{texte, distance, meta}], du plus proche au plus lointain (distance : plus petit = plus proche).
    `date` : ne garde que les chunks de documents en vigueur ce jour-là (filtre de métadonnées)."""
    res = collection.query(query_embeddings=[embeddings([question])[0]], n_results=k if date is None else max(6 * k, 12))
    trouves = [{"texte": t, "distance": d, "meta": m} for t, d, m in zip(res["documents"][0], res["distances"][0], res["metadatas"][0])]
    if date:
        trouves = [p for p in trouves if is_in_force(p["meta"], date)]
    return trouves[:k]


def best_threshold(distances_dans: list[float], distances_hors: list[float]) -> tuple[float, float]:
    """Le seuil de refus (distance maximale acceptée) qui maximise l'exactitude sur un jeu étiqueté, et cette exactitude.
    Un chunk à distance <= seuil est accepté ; au-delà, la question est refusée."""
    points = sorted([(d, True) for d in distances_dans] + [(d, False) for d in distances_hors])
    candidats = [points[0][0] - 1e-6] + [(a[0] + b[0]) / 2 for a, b in zip(points, points[1:])] + [points[-1][0] + 1e-6]
    exactitudes = [sum((d <= s) == dans for d, dans in points) / len(points) for s in candidats]
    meilleurs = [s for s, e in zip(candidats, exactitudes) if e == max(exactitudes)]
    return meilleurs[len(meilleurs) // 2], max(exactitudes)                    # au milieu des seuils équivalents


# ------------------------------------------------------------------ reranking
def rerank(question: str, chunks: list[dict], n: int = 5) -> list[dict]:
    """Reclasse `chunks` avec un modèle de reranking (MODELE_RERANK, via LiteLLM) et renvoie les `n` plus pertinents, du meilleur au moins bon.
    Chaque chunk garde ses champs et reçoit `score` : la pertinence estimée par le reranker (plus grand = plus pertinent)."""
    _require("MODELE_RERANK", "RERANK_API_KEY")
    if not chunks:
        return []
    import litellm
    parametres = {"api_base": os.environ["RERANK_API_BASE"]} if os.getenv("RERANK_API_BASE") else {}
    for tentative in range(8):                                              # limite de débit : on réessaie, avec une attente croissante
        try:
            r = litellm.rerank(model=os.environ["MODELE_RERANK"], query=question, documents=[p["texte"] for p in chunks], top_n=n,
                               api_key=os.environ["RERANK_API_KEY"], **parametres)
            break
        except litellm.RateLimitError:
            if tentative == 7:
                raise
            time.sleep(min(2 ** tentative, 30))
    return [{**chunks[x["index"]], "score": x["relevance_score"]} for x in r.results]


# ------------------------------------------------------------------ génération
# Prompt de réponse par défaut de `build_prompt` : un notebook peut passer le sien.
PROMPT_RAG = """Tu es l'assistant du service client de Lagune Banque.

# Règle 1 - Périmètre strict
Réponds UNIQUEMENT à partir des chunks fournis ci-dessous.
Si l'information n'y figure pas, réponds exactement :
"Je ne trouve pas cette information dans la documentation fournie."
N'invente jamais un chiffre, un délai ou une condition.

# Règle 2 - Citation
Pour chaque affirmation, indique la source entre crochets, par exemple [DOC-06].
Si plusieurs chunks se contredisent, signale-le explicitement.

# Règle 3 - Concision
Réponds en 2 à 4 phrases maximum, style professionnel et direct.

# Chunks fournis
{chunks}

# Question du client
{question}
"""


def format_chunks(chunks: list[dict]) -> str:
    """Les chunks mis bout à bout pour le prompt, chacun précédé de sa source et de sa version."""
    return "\n\n".join(f"[{p['meta']['source']} · version {p['meta']['version']}]\n{p['texte']}" for p in chunks)


def build_prompt(question: str, chunks: list[dict], prompt: str = PROMPT_RAG) -> str:
    """`prompt` rempli avec les chunks et la question (il contient `{chunks}` et `{question}`)."""
    return prompt.format(chunks=format_chunks(chunks), question=question)


def generate(prompt: str) -> str:
    """Réponse du modèle (MODELE) via LiteLLM."""
    _require("MODELE", "LLM_API_KEY")
    import litellm
    litellm.drop_params = True
    r = litellm.completion(model=os.environ["MODELE"], api_key=os.environ["LLM_API_KEY"], temperature=0, max_tokens=400, num_retries=4,
                           messages=[{"role": "user", "content": prompt}])
    return (r.choices[0].message.content or "").strip()
