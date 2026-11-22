"""Dépenses à comparer : sélection, fenêtre de 12 mois, catégories et corrections (étape 2).

Seuls les achats et remboursements de la carte de crédit comptent : les
paiements de la carte et la remise de la carte actuelle ne sont pas des
dépenses, et le relevé du compte est laissé de côté en v1 (risque de double
comptage avec les paiements de carte).
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from src.categories import AUTRE, CATEGORIES, categoriser
from src.desjardins import Transaction

NATURES_GARDEES = {"achat", "remboursement"}


@dataclass(frozen=True)
class Depense:
    date: date
    marchand: str
    montant: Decimal  # négatif pour un remboursement
    categorie: str


def fenetre_12_mois_complets(transactions: list[Transaction]) -> tuple[date, date]:
    """Les 12 mois complets qui précèdent le mois de la dernière transaction
    (ce mois-là est sans doute incomplet au moment de l'export)."""
    if not transactions:
        raise ValueError("Le relevé ne contient aucune transaction.")
    derniere = max(t.date for t in transactions)
    fin = derniere.replace(day=1) - timedelta(days=1)  # dernier jour du mois précédent
    debut = date(fin.year - 1, fin.month, 1) + timedelta(days=32)
    return debut.replace(day=1), fin


def preparer_depenses(transactions: list[Transaction],
                      corrections: dict[str, str] | None = None) -> list[Depense]:
    """Dépenses de carte des 12 derniers mois complets, catégorisées.

    corrections : {marchand: catégorie} choisies à la main ; elles l'emportent sur les règles.
    """
    corrections = corrections or {}
    for marchand, categorie in corrections.items():
        if categorie not in CATEGORIES:
            raise ValueError(f"Correction de « {marchand} » : catégorie inconnue « {categorie} ».")

    debut, fin = fenetre_12_mois_complets(transactions)
    return [
        Depense(t.date, t.marchand, t.montant,
                corrections.get(t.marchand) or categoriser(t.marchand))
        for t in transactions
        if t.source == "carte" and t.nature in NATURES_GARDEES and debut <= t.date <= fin
    ]


def repartir_par_categorie(depenses: list[Depense]) -> dict[str, Decimal]:
    """Total net par catégorie, de la plus grosse à la plus petite."""
    totaux: dict[str, Decimal] = defaultdict(Decimal)
    for d in depenses:
        totaux[d.categorie] += d.montant
    return dict(sorted(totaux.items(), key=lambda item: item[1], reverse=True))


def marchands_non_reconnus(depenses: list[Depense]) -> list[tuple[str, int, Decimal]]:
    """(marchand, nombre de transactions, total) des dépenses restées dans « Autre »,
    les plus gros montants d'abord : ce sont les corrections les plus utiles."""
    nombres: dict[str, int] = defaultdict(int)
    totaux: dict[str, Decimal] = defaultdict(Decimal)
    for d in depenses:
        if d.categorie == AUTRE:
            nombres[d.marchand] += 1
            totaux[d.marchand] += d.montant
    return sorted(((m, nombres[m], totaux[m]) for m in totaux),
                  key=lambda item: item[2], reverse=True)
