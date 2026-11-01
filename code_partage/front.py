"""Interface de chat Gradio commune aux notebooks.

Vous n'écrivez pas l'interface : vous écrivez une fonction `answer(message, historique)` et la branchez avec `create`.
La fonction peut renvoyer (ou produire avec `yield`) une liste de messages : des blocs repliables (chunks utilisés, tools appelés)
suivis de la réponse.
"""
import json
import re
import time
from typing import Callable, Optional

import gradio as gr

# apparence de l'interface, appliquée au lancement (voir `launch`)
THEME = gr.themes.Base(primary_hue="teal", neutral_hue="slate", radius_size="lg",
                       font=[gr.themes.GoogleFont("IBM Plex Sans"), "system-ui", "sans-serif"])
CSS = ".gradio-container {max-width: 980px !important; margin: 0 auto !important}"


# ------------------------------------------------------------------ messages
def text(contenu) -> str:
    """Le texte d'un message de l'historique (Gradio peut le fournir sous forme de blocs)."""
    if isinstance(contenu, str):
        return contenu
    return " ".join(b.get("text", "") for b in contenu if isinstance(b, dict))


def exchanges(historique) -> list[dict]:
    """Les échanges précédents en texte seul, sans les blocs repliables (ceux qui portent un titre)."""
    return [{"role": m["role"], "content": text(m["content"])} for m in historique if not (m.get("metadata") or {}).get("title")]


def without_references(reponse: str) -> str:
    """Retire les références de documents (DOC-xx) : les sources se voient dans les blocs, pas dans le texte."""
    reponse = re.sub(r"[ ,;]*DOC-\d+", "", reponse)
    reponse = re.sub(r"\(\s*\)|\[\s*\]", "", reponse)
    reponse = re.sub(r"\(\s*[,;]\s*", "(", reponse)
    return re.sub(r"\s+([.,;])", r"\1", reponse).strip()


def block(titre: str, contenu: str, id: Optional[str] = None, duree: Optional[float] = None, termine: bool = True) -> gr.ChatMessage:
    """Un bloc repliable dans la conversation. Tant que `termine` est faux, un indicateur d'attente tourne à côté du titre."""
    meta = {"title": titre, "status": "done" if termine else "pending"}
    if id:
        meta["id"] = id
    if duree is not None:
        meta["duration"] = duree
    return gr.ChatMessage(content=contenu, metadata=meta)


def chunks_block(chunks: list[dict], duree: float) -> gr.ChatMessage:
    """Les chunks d'un RAG (`rag.search`) : document, version, distance ou score de reranker, et extrait."""
    def measure(p):
        return " · ".join(f"{nom} {p[cle]:.2f}" for cle, nom in (("distance", "distance"), ("score", "score")) if cle in p)

    detail = "\n\n".join(
        f"**{p['meta']['source']}** · {p['meta']['titre']} (version {p['meta']['version']}) · {measure(p)}\n> {' '.join(p['texte'].split())[:220]}…"
        for p in chunks)
    return block("Chunks utilisés", detail or "Aucun chunk en vigueur à cette date.", duree=duree)


def tool_block(appel: dict, resultat: Optional[str] = None, duree: Optional[float] = None, prefixe: str = "Tool") -> gr.ChatMessage:
    """Un appel de tool : `appel` est un élément de `AIMessage.tool_calls` ; sans `resultat`, le tool est en cours."""
    contenu = f"Arguments : `{json.dumps(appel['args'], ensure_ascii=False)}`"
    if resultat is not None:
        contenu += f"\n\nRésultat : {resultat[:420]}{'…' if len(resultat) > 420 else ''}"
    return block(f"{prefixe} : {appel['name']}", contenu, id=appel["id"], duree=duree, termine=resultat is not None)


# ------------------------------------------------------------------ interface
def create(fn: Callable, titre: str, description: str, accueil: str, exemples: list, champs: Optional[list] = None,
           hauteur: int = 520, titre_champs: str = "Identification (réglée par l'application, pas par le modèle)") -> gr.ChatInterface:
    """Le chat autour de `fn`. `champs` : composants Gradio dont la valeur est passée à `fn` après (message, historique),
    par exemple la liste déroulante du client identifié ; `exemples` contient alors une valeur par champ, après la question."""
    return gr.ChatInterface(
        fn=fn, title=titre, description=description,
        chatbot=gr.Chatbot(label="Conversation", height=hauteur, placeholder=accueil),
        textbox=gr.Textbox(placeholder="Posez votre question…", submit_btn=True, lines=1, max_lines=4),
        additional_inputs=champs,
        additional_inputs_accordion=gr.Accordion(titre_champs, open=True) if champs else None,
        examples=exemples, cache_examples=False)


def rag_chat(answer: Callable, titre: str, description: str, exemples: list) -> gr.ChatInterface:
    """Le chat d'un RAG autour de `answer(question)`, qui renvoie un dict : `reponse`, `chunks` et, s'il y en a, `citations`.
    Il affiche les chunks utilisés, les citations vérifiées, puis la réponse."""
    def chat(message, historique):
        debut = time.time()
        resultat = answer(message)
        blocs = [chunks_block(resultat["chunks"], round(time.time() - debut, 1))]
        if resultat.get("citations"):
            blocs.append(block("Citations vérifiées", "\n\n".join(f"**{c['source']}** : « {c['extrait']} »" for c in resultat["citations"])))
        yield blocs + [gr.ChatMessage(content=without_references(resultat["reponse"]))]

    return create(chat, titre, description, "**Bonjour, comment puis-je vous aider ?**<br>Posez une question sur les produits, les frais ou les procédures.", exemples)


def launch(demo: gr.ChatInterface, hauteur: int = 800, navigateur: bool = False) -> None:
    """Ouvre l'interface sous la cellule (ou dans un onglet avec `navigateur=True`)."""
    demo.launch(inline=not navigateur, inbrowser=navigateur, height=hauteur, theme=THEME, css=CSS, footer_links=[])
