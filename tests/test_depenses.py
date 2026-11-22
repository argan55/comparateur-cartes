"""Tests de la sélection des dépenses, de la fenêtre de 12 mois et des corrections (étape 2)."""

from datetime import date
from decimal import Decimal

import pytest

from src.categories import AUTRE
from src.depenses import (
    Depense,
    fenetre_12_mois_complets,
    marchands_non_reconnus,
    preparer_depenses,
    repartir_par_categorie,
)
from src.desjardins import Transaction


def transaction(jour, marchand, montant, nature="achat", source="carte"):
    return Transaction(date=jour, description=f"{marchand} MONTREAL QC", marchand=marchand,
                       montant=Decimal(montant), nature=nature, source=source)


# --- Fenêtre de 12 mois complets ----------------------------------------------------


def test_fenetre_exclut_le_mois_en_cours_de_la_derniere_transaction():
    transactions = [transaction(date(2025, 6, 3), "IGA", "10"),
                    transaction(date(2026, 11, 19), "IGA", "10")]

    assert fenetre_12_mois_complets(transactions) == (date(2025, 11, 1), date(2026, 10, 31))


def test_fenetre_qui_traverse_le_debut_de_l_annee():
    transactions = [transaction(date(2026, 1, 15), "IGA", "10")]

    assert fenetre_12_mois_complets(transactions) == (date(2025, 1, 1), date(2025, 12, 31))


def test_fenetre_sans_transaction_est_refusee():
    with pytest.raises(ValueError, match="aucune transaction"):
        fenetre_12_mois_complets([])


# --- Sélection et catégorisation ------------------------------------------------------


def test_seuls_les_achats_et_remboursements_de_carte_de_la_fenetre_sont_gardes():
    transactions = [
        transaction(date(2025, 10, 31), "IGA", "1.00"),  # avant la fenêtre
        transaction(date(2025, 11, 1), "IGA", "2.00"),  # premier jour : gardé
        transaction(date(2026, 3, 1), "PAIEMENT CAISSE", "-500", nature="paiement"),
        transaction(date(2026, 3, 2), "REMISE EN ARGENT", "-3", nature="remise"),
        transaction(date(2026, 3, 3), "METRO", "-4.00", nature="remboursement"),
        transaction(date(2026, 3, 4), "Achat Interac", "9", nature="retrait", source="compte"),
        transaction(date(2026, 10, 31), "SHELL", "8.00"),  # dernier jour : gardé
        transaction(date(2026, 11, 19), "IGA", "16.00"),  # mois en cours : exclu
    ]

    depenses = preparer_depenses(transactions)

    assert depenses == [
        Depense(date(2025, 11, 1), "IGA", Decimal("2.00"), "epicerie_reseau_sobeys"),
        Depense(date(2026, 3, 3), "METRO", Decimal("-4.00"), "epicerie"),
        Depense(date(2026, 10, 31), "SHELL", Decimal("8.00"), "essence"),
    ]


def test_marchand_inconnu_est_dans_autre():
    transactions = [transaction(date(2026, 3, 1), "QUINCAILLERIE FICTIVE", "30"),
                    transaction(date(2026, 12, 1), "IGA", "1")]

    assert preparer_depenses(transactions)[0].categorie == AUTRE


# --- Corrections manuelles -----------------------------------------------------------


def test_correction_s_applique_a_toutes_les_transactions_du_marchand():
    transactions = [
        transaction(date(2026, 3, 1), "QUINCAILLERIE FICTIVE", "30"),
        transaction(date(2026, 4, 1), "QUINCAILLERIE FICTIVE", "20"),
        transaction(date(2026, 4, 2), "METRO", "50"),
        transaction(date(2026, 12, 1), "IGA", "1"),
    ]

    depenses = preparer_depenses(transactions, {"QUINCAILLERIE FICTIVE": "divertissement"})

    assert [d.categorie for d in depenses] == ["divertissement", "divertissement", "epicerie"]


def test_correction_peut_remplacer_une_categorie_trouvee_par_les_regles():
    transactions = [transaction(date(2026, 3, 1), "METRO", "30"),
                    transaction(date(2026, 12, 1), "IGA", "1")]

    depenses = preparer_depenses(transactions, {"METRO": AUTRE})

    assert depenses[0].categorie == AUTRE


def test_correction_vers_une_categorie_inconnue_est_refusee():
    transactions = [transaction(date(2026, 3, 1), "METRO", "30")]

    with pytest.raises(ValueError, match="catégorie inconnue.*cinema"):
        preparer_depenses(transactions, {"METRO": "cinema"})


# --- Répartition et marchands non reconnus ----------------------------------------------


DEPENSES = [
    Depense(date(2026, 1, 1), "METRO", Decimal("100.00"), "epicerie"),
    Depense(date(2026, 1, 2), "METRO", Decimal("-10.00"), "epicerie"),
    Depense(date(2026, 1, 3), "SHELL", Decimal("40.50"), "essence"),
    Depense(date(2026, 1, 4), "BOUTIQUE A", Decimal("5.00"), AUTRE),
    Depense(date(2026, 1, 5), "BOUTIQUE B", Decimal("60.00"), AUTRE),
    Depense(date(2026, 2, 5), "BOUTIQUE B", Decimal("15.25"), AUTRE),
]


def test_repartition_additionne_par_categorie_du_plus_gros_au_plus_petit():
    repartition = repartir_par_categorie(DEPENSES)

    assert list(repartition.items()) == [
        ("epicerie", Decimal("90.00")),
        (AUTRE, Decimal("80.25")),
        ("essence", Decimal("40.50")),
    ]


def test_repartition_vide_donne_un_dictionnaire_vide():
    assert repartir_par_categorie([]) == {}


def test_marchands_non_reconnus_tries_par_montant_avec_le_nombre_d_achats():
    assert marchands_non_reconnus(DEPENSES) == [
        ("BOUTIQUE B", 2, Decimal("75.25")),
        ("BOUTIQUE A", 1, Decimal("5.00")),
    ]
