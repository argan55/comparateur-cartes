"""Lecture des relevés CSV exportés d'AccèsD Desjardins (étape 1).

Format observé sur de vrais exports (novembre 2026) :
- aucune ligne d'en-tête, séparateur virgule, UTF-8 (en pratique pur ASCII) ;
- champs vides écrits "" ; la description n'est PAS entre guillemets, donc une
  virgule dans la description ajoute une colonne qu'il faut recoller ;
- dates AAAA/MM/JJ ; montants à point décimal, sans signe ;
- carte de crédit : 13 colonnes, achat en colonne 11, crédit en colonne 12 ;
- compte d'opérations : 16 colonnes, retrait en colonne 7, dépôt en colonne 8 ;
- description de carte en largeur fixe (41 caractères) : marchand sur les
  25 premiers, puis ville (13) et province. Un nom long est tronqué et peut
  coller à la ville, d'où le découpage par position plutôt que par espaces.

On ne garde que ce qui sert au calcul : ni nom de caisse, ni folio, ni numéro
de carte. Le lecteur reçoit le contenu (octets ou texte), jamais un chemin, pour
que l'appli n'ait rien à écrire sur disque.
"""

import csv
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

COLONNE_DATE = 3
COLONNE_DESCRIPTION = 5

# Nombre de colonnes normal → (source, colonne de l'argent qui sort, colonne de l'argent qui revient)
FORMATS = {
    13: ("carte", 11, 12),
    16: ("compte", 7, 8),
}

LARGEUR_MARCHAND_CARTE = 25

UN_CENT = Decimal("0.01")


@dataclass(frozen=True)
class Transaction:
    """Une ligne du relevé.

    montant > 0 : l'argent sort (achat, retrait) ;
    montant < 0 : l'argent revient (paiement de la carte, remboursement, remise, dépôt).
    """

    date: date
    description: str  # description complète, espaces multiples réduits
    marchand: str  # carte : nom du marchand sans la ville ; compte : la description
    montant: Decimal
    nature: str  # carte : achat, frais, remboursement, paiement, remise ; compte : retrait, depot
    source: str  # « carte » ou « compte »


def lire_releve(contenu: bytes | str) -> list[Transaction]:
    """Lit un export CSV Desjardins (carte ou compte) et renvoie ses transactions,
    triées de la plus ancienne à la plus récente."""
    texte = _decoder(contenu)
    lignes = [
        (numero, colonnes)
        for numero, colonnes in enumerate(csv.reader(texte.splitlines()), start=1)
        if any(valeur.strip() for valeur in colonnes)
    ]
    if not lignes:
        raise ValueError("Le fichier est vide.")

    # Les lignes normales ont le moins de colonnes ; les autres ont une virgule dans la description.
    nb_colonnes = min(len(colonnes) for _, colonnes in lignes)
    if nb_colonnes not in FORMATS:
        raise ValueError(
            "Ce fichier n'a pas le format d'un relevé CSV Desjardins "
            f"({nb_colonnes} colonnes au lieu de 13 pour une carte ou 16 pour un compte)."
        )
    source, col_sortie, col_entree = FORMATS[nb_colonnes]

    transactions = [
        _lire_ligne(numero, _recoller_description(colonnes, nb_colonnes),
                    source, col_sortie, col_entree)
        for numero, colonnes in lignes
    ]
    # sorted est stable : deux transactions du même jour gardent l'ordre du fichier.
    return sorted(transactions, key=lambda t: t.date)


def _decoder(contenu: bytes | str) -> str:
    if isinstance(contenu, str):
        return contenu.removeprefix("﻿")
    try:
        return contenu.decode("utf-8-sig")
    except UnicodeDecodeError:
        # Anciens exports ou fichier réenregistré par Excel sous Windows.
        return contenu.decode("cp1252")


def _recoller_description(colonnes: list[str], nb_colonnes: int) -> list[str]:
    en_trop = len(colonnes) - nb_colonnes
    if en_trop == 0:
        return colonnes
    fin_description = COLONNE_DESCRIPTION + en_trop + 1
    description = ",".join(colonnes[COLONNE_DESCRIPTION:fin_description])
    return colonnes[:COLONNE_DESCRIPTION] + [description] + colonnes[fin_description:]


def _lire_ligne(numero: int, colonnes: list[str], source: str,
                col_sortie: int, col_entree: int) -> Transaction:
    try:
        jour = datetime.strptime(colonnes[COLONNE_DATE].strip(), "%Y/%m/%d").date()
    except ValueError:
        raise ValueError(
            f"Relevé, ligne {numero} : date illisible « {colonnes[COLONNE_DATE]} » "
            "(attendu AAAA/MM/JJ)."
        ) from None

    brute = colonnes[COLONNE_DESCRIPTION]
    description = " ".join(brute.split())
    if source == "carte":
        marchand = " ".join(brute[:LARGEUR_MARCHAND_CARTE].split())
    else:
        marchand = description
    sortie = _lire_montant(numero, colonnes[col_sortie])
    entree = _lire_montant(numero, colonnes[col_entree])

    if sortie is None and entree is None:
        raise ValueError(f"Relevé, ligne {numero} : aucun montant.")
    if sortie is not None and entree is not None:
        raise ValueError(f"Relevé, ligne {numero} : deux montants (sortie et entrée) sur la même ligne.")

    if sortie is not None:
        montant = sortie
        if source == "compte":
            nature = "retrait"
        elif description.upper().startswith("FRAIS DE CREDIT"):
            nature = "frais"  # intérêts et frais de la carte : pas une dépense à comparer
        else:
            nature = "achat"
    else:
        montant = -entree
        nature = _nature_du_credit(description) if source == "carte" else "depot"

    return Transaction(date=jour, description=description, marchand=marchand,
                       montant=montant, nature=nature, source=source)


def _lire_montant(numero: int, valeur: str) -> Decimal | None:
    valeur = valeur.strip()
    if not valeur:
        return None
    try:
        montant = Decimal(valeur)
    except InvalidOperation:
        montant = None
    if montant is None or not montant.is_finite():
        raise ValueError(f"Relevé, ligne {numero} : montant illisible « {valeur} ».")
    return montant.quantize(UN_CENT, rounding=ROUND_HALF_UP)


def _nature_du_credit(description: str) -> str:
    """Un crédit sur la carte : paiement, remise de la carte actuelle ou remboursement d'un marchand."""
    en_majuscules = description.upper()
    if "PAIEMENT" in en_majuscules:
        return "paiement"
    if "REMISE" in en_majuscules:
        return "remise"
    return "remboursement"
