"""Fonctions métier : lecture et écriture de la base, recherche dans la documentation. Du Python et du SQL, sans
modèle, testables seules. Les tools de l'agent les appellent."""
import json
from datetime import datetime, timedelta

from base import AUJOURDHUI, connect
from doc_search import find_docs


def fetch_loans(client_id):
    """Prêts du client : produit, montant, statut, solde restant et suspension."""
    with connect() as con:
        return {"prets": [dict(r) for r in con.execute(
            "SELECT pret_id, produit, montant, frais_service, date_octroi, duree_jours, statut, solde_restant, suspension "
            "FROM prets WHERE client_id = ? ORDER BY date_octroi", (client_id,))]}


def fetch_schedule(client_id, pret_id=None):
    """Échéancier des prêts en cours ou impayés du client (ou du seul `pret_id`)."""
    with connect() as con:
        prets = con.execute("SELECT * FROM prets WHERE client_id = ? AND statut IN ('en_cours', 'impaye') "
                            "AND (? IS NULL OR pret_id = ?)", (client_id, pret_id, pret_id)).fetchall()
        if not prets:
            return {"erreur": "Aucun prêt en cours pour ce client."}
        return {"date_du_jour": AUJOURDHUI, "prets": [
            {"pret_id": p["pret_id"], "produit": p["produit"], "solde_restant": p["solde_restant"],
             "suspension": bool(p["suspension"]),
             "echeances": [dict(e) for e in con.execute(
                 "SELECT echeance_id, pret_id, numero, date_echeance, montant_du, montant_paye, statut, frais_retard "
                 "FROM echeances WHERE pret_id = ? ORDER BY numero", (p["pret_id"],))]} for p in prets]}


def fetch_lm_transactions(client_id, date, montant=None):
    """Remboursements Lagune Money du client, de la veille de `date` (AAAA-MM-JJ) à son surlendemain exclu."""
    jour = datetime.fromisoformat(date[:10])
    debut, fin = (jour - timedelta(days=1)).date().isoformat(), (jour + timedelta(days=2)).date().isoformat()
    with connect() as con:
        lignes = con.execute(
            "SELECT transaction_id, montant, date_heure, statut, code_echec, echeance_rattachee, libelle FROM transactions_om "
            "WHERE client_id = ? AND type = 'remboursement_pret' AND date_heure >= ? AND date_heure < ? "
            "AND (? IS NULL OR montant = ?) ORDER BY date_heure", (client_id, debut, fin, montant, montant)).fetchall()
    return {"transactions": [dict(t) for t in lignes]}


def fetch_incidents(date_heure):
    """Incidents de la plateforme qui couvrent `date_heure` (AAAA-MM-JJTHH:MM), et ceux du même jour."""
    with connect() as con:
        couvrants = con.execute("SELECT * FROM incidents_plateforme WHERE debut <= ? AND fin >= ?", (date_heure, date_heure)).fetchall()
        meme_jour = con.execute("SELECT * FROM incidents_plateforme WHERE substr(debut, 1, 10) = ?", (date_heure[:10],)).fetchall()
    return {"date_heure": date_heure, "incidents_a_cette_heure": [dict(r) for r in couvrants],
            "incidents_du_jour": [dict(r) for r in meme_jour]}


def fetch_docs(requete, date_reference=None, k=3):
    """Recherche dans la documentation (index du module 2), limitée aux documents en vigueur à `date_reference`."""
    date_reference = date_reference or AUJOURDHUI
    return {"date_reference": date_reference, "resultats": find_docs(requete, date_reference, k)}


def insert_claim(client_id, parcours, resume, demande_client, elements_verifies, urgence,
                  pret_id=None, echeance_id=None, transaction_id=None, incident_id=None):
    """Enregistre une réclamation avec son dossier pour un conseiller ; date limite de traitement : 72 heures."""
    dossier = {"schema_version": "1.0", "client_id": client_id, "parcours": parcours, "resume": resume,
               "demande_client": demande_client, "elements_verifies": elements_verifies, "pret_id": pret_id,
               "echeance_id": echeance_id, "transaction_id": transaction_id, "incident_id": incident_id,
               "actions_agent": ["transfert au conseiller"] if parcours == "P5" else ["réclamation créée"], "urgence": urgence}
    maintenant = datetime.fromisoformat(AUJOURDHUI + "T10:00:00")
    limite = (maintenant + timedelta(hours=72)).isoformat()
    with connect() as con:
        ref = f"REC-{con.execute('SELECT COUNT(*) FROM reclamations').fetchone()[0] + 1:04d}"
        con.execute("INSERT INTO reclamations VALUES (?,?,?,?,?,?,?,?)",
                    (ref, client_id, maintenant.isoformat(), parcours, resume, "ouverte", limite, json.dumps(dossier, ensure_ascii=False)))
    return {"reclamation_id": ref, "date_limite": limite, "dossier": dossier}


def apply_regularisation(client_id, validateur, echeance_id, transaction_id, incident_id, justification):
    """Régularise une échéance à partir d'un remboursement non rattaché. Sans validateur, ne modifie rien. Sinon,
    revérifie les conditions de la procédure DOC-08 sans faire confiance au modèle, puis rattache la transaction,
    annule les frais de retard, lève la suspension et inscrit la régularisation avec son validateur."""
    if not validateur:
        return {"statut": "en_attente_validation",
                "message": "Action à incidence financière : validation par un conseiller obligatoire. Aucune modification effectuée."}
    with connect() as con:
        tx = con.execute("SELECT * FROM transactions_om WHERE transaction_id = ?", (transaction_id,)).fetchone()
        ech = con.execute("SELECT e.*, p.client_id FROM echeances e JOIN prets p USING (pret_id) WHERE e.echeance_id = ?",
                          (echeance_id,)).fetchone()
        refus = None
        if not (justification or "").strip():
            refus = "Justification obligatoire (procédure DOC-08)."
        elif tx is None or tx["client_id"] != client_id or tx["type"] != "remboursement_pret":
            refus = "Transaction de remboursement introuvable pour ce client."
        elif tx["statut"] != "reussie":
            refus = "La transaction a échoué : aucun paiement n'a été reçu."
        elif tx["echeance_rattachee"] is not None:
            refus = "La transaction est déjà rattachée à une échéance."
        elif ech is None or ech["client_id"] != client_id or ech["statut"] != "impayee":
            refus = "L'échéance n'est pas une échéance impayée de ce client."
        elif tx["montant"] != ech["montant_du"]:
            refus = "Le montant de la transaction ne correspond pas à l'échéance."
        if refus:
            return {"statut": "refusee", "message": refus}
        maintenant = AUJOURDHUI + "T10:00:00"
        con.execute("UPDATE transactions_om SET echeance_rattachee = ? WHERE transaction_id = ?", (echeance_id, transaction_id))
        con.execute("UPDATE echeances SET statut = 'regularisee', montant_paye = montant_du, frais_retard = 0, date_paiement = ? "
                    "WHERE echeance_id = ?", (tx["date_heure"], echeance_id))
        reste = con.execute("SELECT COUNT(*) FROM echeances WHERE pret_id = ? AND statut IN ('impayee', 'a_venir')",
                            (ech["pret_id"],)).fetchone()[0]
        con.execute("UPDATE prets SET solde_restant = MAX(0, solde_restant - ?), suspension = 0, "
                    "statut = CASE WHEN ? = 0 THEN 'regularise' ELSE 'en_cours' END WHERE pret_id = ?",
                    (ech["montant_du"], reste, ech["pret_id"]))
        reg = f"REG-{con.execute('SELECT COUNT(*) FROM regularisations').fetchone()[0] + 1:04d}"
        con.execute("INSERT INTO regularisations VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (reg, client_id, echeance_id, transaction_id,
                     "Rattachement de la transaction ; annulation des frais de retard ; levée de la suspension",
                     ech["frais_retard"], "validee", "agent", validateur, maintenant, maintenant, justification))
    return {"statut": "validee", "regularisation_id": reg, "transaction_id": transaction_id, "echeance_id": echeance_id,
            "frais_annules": ech["frais_retard"], "validateur": validateur}
