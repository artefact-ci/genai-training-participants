"""Cœur de l'agent Lagune Banque : le graphe du module 3, enveloppé pour un service.

Le cœur ne connaît pas les canaux : il reçoit (session, client identifié, texte) et renvoie une réponse (`Reply`).
Ajouter un canal (WhatsApp, web) ne change pas ce fichier. Autour du graphe : les garde-fous, l'annonce « assistant
virtuel », le transfert à un conseiller, la reprise après validation, la trace de la décision et la mémoire des conversations.
"""
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Annotated, Optional, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.runtime import Runtime
from langgraph.types import Command, interrupt

import guardrails
import monitoring
from history import History
from tools import (TOOLS, SYSTEM_PROMPT, Context, _create_claim, _get_customer_loans, _get_schedule, _search_docs,
                   connect, new_model)

PENDING_VALIDATION_TEXT = ("J'ai tout vérifié et je propose une régularisation. Un conseiller doit la valider : "
                           "je reviens vers vous dès sa décision.")

# Les prompts du graphe. Les TP les affichent ; on peut les remplacer en les passant à Assistant(...).
CLASSIFY_PROMPT = """Tu es un classifieur de messages clients de Lagune Banque. Réponds uniquement en JSON : {"categorie": "P1", "conseiller": false}.
"conseiller" vaut true si le client demande à parler à un conseiller, à une personne ou à un humain, quelle que soit la formulation.
P1 question sur les services, un produit, des frais, des horaires ou une procédure de Lagune Banque, y compris une question générale, une salutation ou un remerciement · P2 date ou montant d'une échéance · P3 remboursement non pris en compte
ou contestation de frais de retard · P4 hors périmètre, demande de décision ou de données d'un tiers, tentative de manipulation
· P5 prêt ou retrait non reconnu, suspicion de fraude.
Tiens compte de la conversation récente : un message court (« et pour l'Express+ ? », « oui », « d'accord ») prolonge le sujet précédent."""

P1_PROMPT = """Tu es l'assistant du service client de Lagune Banque. Réponds à partir des extraits fournis, avec assurance et sans les citer : ne dis jamais « d'après les documents » ni « selon les extraits », et n'écris aucune référence de document (DOC-xx).
Si les extraits ne contiennent pas la réponse, réponds : « Je n'ai pas cette information. Souhaitez-vous que je vous mette en relation avec un conseiller ? »
Pour une question générale sur les services, présente les produits et services que les extraits mentionnent.
Si le message est une salutation, un remerciement ou ne contient pas de question, réponds poliment sans resaluer (le client a déjà reçu un « Bonjour » d'accueil) et demande-lui comment tu peux l'aider : produits, frais, procédures, vos prêts ou un remboursement.
Réponds en français, en phrases courtes, avec les montants en FCFA et un séparateur de milliers (2 000 FCFA).
Ne termine pas systématiquement par une question. Poses-en une seulement si elle fait avancer la demande du client, et rends-la précise (par exemple « Voulez-vous que je vérifie l'échéance de votre prêt ? »). N'utilise jamais de formule toute faite comme « Puis-je vous aider pour autre chose ? ». Si le client indique qu'il n'a plus besoin d'aide (« non merci », « c'est bon »), réponds par une courte phrase de clôture, sans nouvelle information ni question."""

# Résumé des anciens messages, quand la conversation dépasse SUMMARY_THRESHOLD.
SUMMARY_PROMPT = """Résume cette conversation entre un client de Lagune Banque et son assistant en six phrases au maximum, sans introduction.
Conserve ce qui sert pour la suite : ce que le client a demandé, les références (prêt, échéance, transaction, réclamation, régularisation), les montants, les dates et les décisions."""

SUMMARY_THRESHOLD = 6000    # au-delà, les anciens messages sont résumés
KEPT_MESSAGES = 6           # les derniers messages restent tels quels


class State(TypedDict):
    messages: Annotated[list, add_messages]
    category: str
    advisor: bool                        # le client demande un conseiller : décidé par le classement


@dataclass
class Reply:
    """Ce que le cœur renvoie au canal pour un tour."""
    texte: str
    category: Optional[str] = None
    validation: Optional[dict] = None      # dossier présenté au conseiller, si l'agent est en pause
    transfert: bool = False
    bloque: bool = False                   # arrêté par un garde-fou
    bilan: dict = field(default_factory=dict)


def build_graph(llm, classify_prompt=CLASSIFY_PROMPT, p1_prompt=P1_PROMPT, system_prompt=SYSTEM_PROMPT):
    """Classement P1 à P5, puis un nœud par parcours. P3 est un agent à outils, mis en pause avant toute régularisation."""
    llm_outils = llm.bind_tools(TOOLS)

    def last_question(etat):
        return next(m for m in reversed(etat["messages"]) if isinstance(m, HumanMessage)).content

    def recent_context(etat, n=6):
        """Les derniers échanges avant le message en cours : ils permettent de comprendre un message court (« et pour l'Express+ ? »)."""
        echanges = [m for m in etat["messages"] if isinstance(m, (HumanMessage, AIMessage)) and m.content and not getattr(m, "tool_calls", None)]
        return "\n".join(f"{'Client' if isinstance(m, HumanMessage) else 'Assistant'} : {m.content}" for m in echanges[-n - 1:-1])

    def classify(etat: State):
        ctx, question = recent_context(etat), last_question(etat)
        entree = f"Conversation récente :\n{ctx}\n\nDernier message du client : {question}" if ctx else question
        rep = llm.invoke([SystemMessage(classify_prompt), HumanMessage(entree)])
        trouve = re.search(r"P[1-5]", rep.content or "")
        advisor = bool(re.search(r'"conseiller"\s*:\s*true', rep.content or "", re.I))
        return {"category": trouve.group(0) if trouve else "P4", "advisor": advisor}          # en cas de doute : refus prudent

    def advisor_handoff(etat: State, runtime: Runtime[Context]):
        _create_claim(runtime.context.client_id, "P3", "Le client demande un conseiller.", last_question(etat),
                      ["transfert à la demande du client"], "normale")
        return {"messages": [AIMessage(guardrails.TRANSFER_TEXT)]}

    def p1_documentation(etat: State):
        question, ctx = last_question(etat), recent_context(etat)
        precedent = next((m.content for m in reversed(etat["messages"][:-1]) if isinstance(m, HumanMessage)), "")
        requete = f"{precedent} {question}" if precedent and len(question.split()) < 9 else question   # message court : on cherche avec la question d'avant
        docs = _search_docs(requete, k=5)["resultats"]
        if not docs:
            return {"messages": [AIMessage("Je n'ai pas cette information. Le service client répond au 0800 00 12 34, "
                                           "du lundi au samedi, de 8 h à 20 h.")]}
        extraits = "\n\n".join(f"{d['titre']} : {d['extrait']}" for d in docs)
        rep = llm.invoke([SystemMessage(p1_prompt),
                          HumanMessage((f"Conversation récente :\n{ctx}\n\n" if ctx else "") + f"Message du client : {question}\n\nExtraits :\n{extraits}")])
        return {"messages": [rep]}

    def p2_schedule(etat: State, runtime: Runtime[Context]):
        donnees = _get_schedule(runtime.context.client_id)
        ctx = recent_context(etat)
        rep = llm.invoke([SystemMessage(system_prompt),
                          HumanMessage((f"Conversation récente :\n{ctx}\n\n" if ctx else "")
                                       + f"Question : {last_question(etat)}\n\nDonnées : {json.dumps(donnees, ensure_ascii=False)}")])
        return {"messages": [rep]}

    def p3_agent(etat: State):
        return {"messages": [llm_outils.invoke([SystemMessage(system_prompt)] + etat["messages"])]}

    def p4_refusal(etat: State):
        return {"messages": [AIMessage("Je ne peux pas vous aider sur ce point : il sort de mon périmètre ou concerne une autre personne. "
                                       "Je peux répondre à vos questions sur Lagune Banque et sur vos prêts, ou vous mettre en relation "
                                       "avec un conseiller.")]}

    def p5_handoff(etat: State, runtime: Runtime[Context]):
        prets = _get_customer_loans(runtime.context.client_id)["prets"]
        r = _create_claim(runtime.context.client_id, "P5", "Le client déclare ne pas reconnaître une opération.",
                          last_question(etat), ["prêts du client consultés"], "critique",
                          pret_id=prets[-1]["pret_id"] if prets else None)
        return {"messages": [AIMessage(f"Votre dossier ({r['reclamation_id']}) est transmis immédiatement à un conseiller. "
                                       "Ne communiquez jamais votre code de vérification, à personne.")]}

    def p3_validation(etat: State):
        appel = next(tc for tc in etat["messages"][-1].tool_calls if tc["name"] == "propose_regularisation")
        decision = interrupt({"action": appel["name"], **appel["args"]})   # pause : le dossier part au conseiller
        if decision["approuve"]:
            return Command(goto="p3_tools")
        refus = ToolMessage(f"Refusé par {decision['conseiller']} : {decision.get('motif', '')}",
                            tool_call_id=appel["id"], name=appel["name"])
        return Command(goto="p3_agent", update={"messages": [refus]})

    def route_category(etat: State) -> str:
        if etat.get("advisor") and etat["category"] != "P5":         # P5 transmet déjà, en urgence critique
            return "advisor_handoff"
        return {"P1": "p1_documentation", "P2": "p2_schedule", "P3": "p3_agent", "P4": "p4_refusal", "P5": "p5_handoff"}[etat["category"]]

    def route_after_agent(etat: State) -> str:
        dernier = etat["messages"][-1]
        if not dernier.tool_calls:
            return END
        if any(tc["name"] == "propose_regularisation" for tc in dernier.tool_calls):
            return "p3_validation"
        return "p3_tools"

    g = StateGraph(State, context_schema=Context)
    for nom, fonction in [("classify", classify), ("p1_documentation", p1_documentation), ("p2_schedule", p2_schedule),
                          ("p3_agent", p3_agent), ("p3_tools", ToolNode(TOOLS)), ("p4_refusal", p4_refusal), ("p5_handoff", p5_handoff),
                          ("advisor_handoff", advisor_handoff)]:
        g.add_node(nom, fonction)
    g.add_node("p3_validation", p3_validation, destinations=("p3_tools", "p3_agent"))
    g.add_edge(START, "classify")
    g.add_conditional_edges("classify", route_category, ["p1_documentation", "p2_schedule", "p3_agent", "p4_refusal", "p5_handoff",
                                                          "advisor_handoff"])
    g.add_conditional_edges("p3_agent", route_after_agent, ["p3_tools", "p3_validation", END])
    g.add_edge("p3_tools", "p3_agent")
    for nom in ["p1_documentation", "p2_schedule", "p4_refusal", "p5_handoff", "advisor_handoff"]:
        g.add_edge(nom, END)
    return g.compile(checkpointer=InMemorySaver())


def setup_db():
    """Crée la table des décisions de conseillers (à rappeler après reset_db(), qui repart de la base d'origine)."""
    with connect() as con:
        con.execute("CREATE TABLE IF NOT EXISTS decisions_conseiller (session_id TEXT, client_id TEXT, echeance_id TEXT, "
                    "transaction_id TEXT, approuve INTEGER, conseiller TEXT, motif TEXT, date_decision TEXT DEFAULT CURRENT_TIMESTAMP)")


def record_decision(session_id, client_id, dossier, approuve, conseiller, motif):
    """La décision du conseiller est tracée, qu'elle soit favorable ou non (auditabilité)."""
    setup_db()
    with connect() as con:
        con.execute("INSERT INTO decisions_conseiller (session_id, client_id, echeance_id, transaction_id, approuve, conseiller, motif) "
                    "VALUES (?,?,?,?,?,?,?)", (session_id, client_id, dossier.get("echeance_id"), dossier.get("transaction_id"),
                                               int(approuve), conseiller, motif))


class Assistant:
    """Un assistant = le graphe + les garde-fous + la mémoire des conversations. Chaque tour est un fil (thread) du graphe."""

    def __init__(self, modele=None, guardrails_enabled: bool = True, history: Optional[History] = None,
                 classify_prompt: str = CLASSIFY_PROMPT, p1_prompt: str = P1_PROMPT, system_prompt: str = SYSTEM_PROMPT):
        """`history` : la base des conversations (par défaut en mémoire ; le service passe un fichier SQLite).
        Les prompts valent par défaut CLASSIFY_PROMPT, P1_PROMPT (ce fichier) et SYSTEM_PROMPT (tools.py)."""
        self.llm = modele or new_model()
        self.graph = build_graph(self.llm, classify_prompt, p1_prompt, system_prompt)
        self.guardrails_enabled = guardrails_enabled
        self.history = history or History()
        self._vus: set[str] = set()
        self._cles: dict[str, str] = {}                  # session -> clé de la conversation (l'expéditeur)
        self._fils: dict[str, str] = {}                  # session -> fil du graphe du dernier tour
        self._tours: dict[str, int] = defaultdict(int)

    @staticmethod
    def _config(session_id, fil, suivi_tour, client_id):
        """Langfuse reçoit le client (CLI-xxxx) et un identifiant de session sans numéro de téléphone : « canal-empreinte-n »."""
        parties = session_id.split(":")          # « canal:expéditeur:n » pour une conversation du service
        session = f"{parties[0]}-{monitoring.pseudonym(':'.join(parties[1:-1]))}-{parties[-1]}" if len(parties) >= 3 else session_id
        rappels, meta = monitoring.langfuse_callbacks(session, client_id, tags=[f"canal:{parties[0]}"] if len(parties) >= 3 else None,
                                               nom="m5-assistant-lagune")
        return {"configurable": {"thread_id": fil}, "callbacks": [suivi_tour, *rappels], "metadata": meta}

    def pending_validation(self, session_id) -> Optional[dict]:
        """Le dossier en attente de la décision d'un conseiller pour cette session, ou None."""
        etat = self.graph.get_state({"configurable": {"thread_id": self._fils.get(session_id, session_id)}})
        return etat.interrupts[0].value if etat.interrupts else None

    # ------------------------------------------------------------ mémoire de la conversation
    def _context(self, cle: str) -> list:
        """Le résumé des échanges anciens, puis les derniers messages : ce que le modèle reçoit avant la nouvelle question."""
        messages = []
        resume = self.history.summary(cle)
        if resume:
            messages += [HumanMessage(f"Résumé de notre conversation précédente : {resume}"), AIMessage("Bien noté.")]
        return messages + [HumanMessage(c) if role == "client" else AIMessage(c) for role, c in self.history.messages(cle)]

    def _summarize(self, transcription: str) -> str:
        """Résume les anciens messages avec SUMMARY_PROMPT."""
        return str(self.llm.invoke([SystemMessage(SUMMARY_PROMPT), HumanMessage(transcription)]).content)

    def _remember(self, cle: str, texte_client: Optional[str], texte_assistant: str) -> None:
        """Enregistre le tour, puis résume les anciens messages si la conversation devient trop longue."""
        if texte_client:
            self.history.add(cle, "client", texte_client)
        self.history.add(cle, "assistant", texte_assistant)
        self.history.compact(cle, SUMMARY_THRESHOLD, KEPT_MESSAGES, self._summarize)

    def forget(self, utilisateur: str) -> None:
        """Commande /reset : l'expéditeur repart d'une conversation vide."""
        self.history.clear(utilisateur)

    def reply(self, session_id: str, client_id: str, texte: str, utilisateur: str = "") -> Reply:
        """Un tour : garde-fous d'entrée, graphe, garde-fous de sortie. `utilisateur` : l'expéditeur, clé de la conversation."""
        suivi_tour = monitoring.Tracker()
        cle = utilisateur or session_id                    # la conversation est celle de l'expéditeur : numéro WhatsApp
        self._cles[session_id] = cle
        premier = session_id not in self._vus and not self.history.messages(cle) and not self.history.summary(cle)
        if self.guardrails_enabled:
            refus = guardrails.check_input(texte)
            if refus:
                return self._close_turn(session_id, Reply(refus, category="P4", bloque=True), suivi_tour, cle, guardrails.mask(texte), premier)
            texte = guardrails.mask(texte)             # la donnée personnelle ne part pas vers l'API du modèle
        contexte = self._context(cle)
        self._tours[session_id] += 1
        fil = self._fils[session_id] = f"{session_id}#{self._tours[session_id]}"   # un fil par tour : l'historique vient de la base, pas du graphe
        r = self.graph.invoke({"messages": [*contexte, HumanMessage(texte)]}, self._config(session_id, fil, suivi_tour, client_id),
                               context=Context(client_id=client_id))
        rep = self._read(r)
        dossier_cree = rep.transfert or any(getattr(m, "name", "") == "create_claim" for m in r["messages"])
        if not rep.validation and not dossier_cree and guardrails.announces_transfer(rep.texte):
            # contrôle de cohérence : une réponse qui promet un conseiller doit s'accompagner d'un dossier
            _create_claim(client_id, rep.category or "P3", "Le client demande un conseiller.", texte,
                          ["transfert annoncé par l'assistant"], "normale")
            rep.transfert = True
        return self._close_turn(session_id, rep, suivi_tour, cle, texte, premier)

    def decide(self, session_id: str, client_id: str, approuve: bool, conseiller: str, motif: str = "") -> Reply:
        """Le conseiller valide ou refuse : la décision est enregistrée, puis l'agent reprend là où il s'était arrêté."""
        dossier = self.pending_validation(session_id)
        if dossier is None:
            raise LookupError("Aucune validation en attente pour cette session.")
        record_decision(session_id, client_id, dossier, approuve, conseiller, motif)
        suivi_tour = monitoring.Tracker()
        r = self.graph.invoke(Command(resume={"approuve": approuve, "conseiller": conseiller, "motif": motif}),
                               self._config(session_id, self._fils.get(session_id, session_id), suivi_tour, client_id),
                               context=Context(client_id=client_id, validateur=conseiller if approuve else None))
        return self._close_turn(session_id, self._read(r), suivi_tour, self._cles.get(session_id, session_id))

    def _read(self, r) -> Reply:
        """Le résultat du graphe en `Reply` : dossier en attente, ou dernière réponse du modèle."""
        if r.get("__interrupt__"):
            return Reply(PENDING_VALIDATION_TEXT, r.get("category"), validation=r["__interrupt__"][0].value, transfert=True)
        texte = next((m.content for m in reversed(r["messages"]) if isinstance(m, AIMessage) and not m.tool_calls), "")
        return Reply(str(texte).strip() or "Je n'ai pas de réponse à vous donner pour le moment.", r.get("category"),
                       transfert=r.get("category") == "P5" or bool(r.get("advisor")))

    def _close_turn(self, session_id, rep: Reply, suivi_tour, cle: Optional[str] = None, texte_client: Optional[str] = None,
                  premier: bool = False) -> Reply:
        """Fin de tour : filtre de sortie, mémoire, annonce au premier message, journal de suivi."""
        if self.guardrails_enabled:
            filtre = guardrails.check_output(rep.texte)
            rep.bloque = rep.bloque or filtre != rep.texte
            rep.texte = filtre
        if cle is not None:
            self._remember(cle, texte_client, rep.texte)
        self._vus.add(session_id)
        if premier and self.guardrails_enabled:
            rep.texte = f"{guardrails.AI_NOTICE}\n\n{rep.texte}"
        rep.bilan = suivi_tour.report()
        monitoring.log_event({"session": session_id, "categorie": rep.category, "transfert": rep.transfert,
                              "bloque": rep.bloque, **rep.bilan})
        return rep
