"""Interface de chat Gradio (code_partage/front.py) autour d'un agent ou d'un graphe : un bloc par tool appelé."""
import time

import gradio as gr
from langchain_core.messages import AIMessage, ToolMessage

import front
from base import KOUASSI, Context
from observability import clear_langfuse, langfuse_callbacks

CLIENTS = ["CLI-0002", "CLI-0001", "CLI-0003", "CLI-0004"]  # clients proposés dans la liste déroulante


def respond(agent, tag: str = "m3", name: str = "m3-front-agent", thread: bool = False):
    """Fonction de réponse du chat. Sans `thread`, tout l'historique est renvoyé à chaque message ; avec `thread=True`,
    l'agent garde l'historique dans son checkpointer et ne reçoit que le dernier message. `tag` et `name` étiquettent
    les traces Langfuse."""
    def fn(message, historique, client_id, request: gr.Request):
        session = f"front-{request.session_hash[:8]}"
        messages = [{"role": "user", "content": message}]
        if not thread:
            messages = front.exchanges(historique) + messages
        callbacks, meta = langfuse_callbacks(session_id=session, utilisateur=client_id, tags=["front", tag], nom=name)
        config = {"callbacks": callbacks, "metadata": meta, "configurable": {"thread_id": session}}
        blocs, appels, departs, final = {}, {}, {}, ""
        for event in agent.stream({"messages": messages}, config, context=Context(client_id=client_id), stream_mode="updates"):
            if "__interrupt__" in event:
                final = "En attente de la validation d'un conseiller : aucune action n'a été exécutée."
            for data in event.values():
                if not isinstance(data, dict):
                    continue
                for m in data.get("messages", []):
                    if isinstance(m, AIMessage) and m.tool_calls:
                        for call in m.tool_calls:
                            appels[call["id"]], departs[call["id"]] = call, time.time()
                            blocs[call["id"]] = front.tool_block(call)
                    elif isinstance(m, ToolMessage):
                        blocs[m.tool_call_id] = front.tool_block(appels[m.tool_call_id], str(m.content), round(time.time() - departs[m.tool_call_id], 1))
                    elif isinstance(m, AIMessage):
                        final = front.without_references(str(m.content))
            yield list(blocs.values()) + ([gr.ChatMessage(content=final)] if final else [])
        clear_langfuse()
    return fn


def create(agent, titre: str = "Assistant Lagune Banque : l'agent au travail", **options):
    """Crée l'interface autour de `agent`, à lancer avec `front.launch`. `options` : voir `respond`."""
    return front.create(
        respond(agent, **options),
        titre=titre,
        description="Chaque tool appelé par l'agent s'affiche sous forme de bloc, avec ses arguments et son résultat. "
                    "Le client identifié se choisit dans la liste (données fictives).",
        accueil="**Bonjour, comment puis-je vous aider ?**<br>Décrivez votre situation : l'agent consulte vos prêts et la documentation.",
        champs=[gr.Dropdown(CLIENTS, value="CLI-0002", label="Client identifié")],
        exemples=[[KOUASSI, "CLI-0002"], ["Quand est ma prochaine échéance ?", "CLI-0002"],
                  ["Quels sont les frais de retard du Prêt Express ?", "CLI-0002"]],
        hauteur=560)
