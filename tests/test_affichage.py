"""Tests de la mise en forme pour l'interface (étape 4)."""

from datetime import date
from decimal import Decimal

import pytest

from src.affichage import (
    COLONNE_CATEGORIE, ESPACE, MarchandACorriger, appliquer_modifications, barres_classement,
    corrections_en_csv, formater_cents, formater_montant, formater_pct, lignes_classement,
    lignes_corrections, lignes_detail, lignes_repartition, lire_corrections_csv,
    marchands_a_corriger, notes_detail, periode, phrase_synthese, pour_markdown, valeur_du_point,
)
from src.calcul import DetailCategorie, ResultatCarte
from src.cartes import Carte, Taux
from src.depenses import Depense
from src.desjardins import lire_releve
from tests.fictif import releve_fictif_annuel

D = Decimal
S = ESPACE


def carte(id="c", nom=None, type_recompense="remise", valeur_point="100", frais="0"):
    return Carte(id=id, nom=nom or f"Carte {id}", type_recompense=type_recompense,
                 valeur_point_cents=D(valeur_point), frais_annuels=D(frais),
                 taux=(Taux("autres", D("0.01")),))


def resultat(id, net, frais="0", detail=None, choisies=(), plafonds=()):
    c = carte(id, frais=frais)
    return ResultatCarte(carte=c, recompenses=D(net) + D(frais), frais=D(frais),
                         valeur_nette=D(net), detail=detail or {},
                         categories_choisies=choisies, plafonds_atteints=plafonds)


# --- Nombres et dates -------------------------------------------------------------

@pytest.mark.parametrize("montant, attendu", [
    ("1234.5", f"1{S}234,50{S}$"),
    ("0", f"0,00{S}$"),
    ("0.005", f"0,01{S}$"),  # arrondi au cent, moitié vers le haut
    ("1234567.891", f"1{S}234{S}567,89{S}$"),
    ("-191.88", f"-191,88{S}$"),
])
def test_montant_a_la_quebecoise(montant, attendu):
    assert formater_montant(D(montant)) == attendu


def test_pourcentage_et_cents():
    assert formater_pct(D("0.0125")) == f"1,25{S}%"
    assert formater_cents(D("0.71")) == f"0,71{S}¢"


def test_les_dollars_sont_echappes_pour_markdown():
    assert pour_markdown(f"1,00{S}$ et 2,00{S}$") == f"1,00{S}\\$ et 2,00{S}\\$"


def test_periode_en_mois_francais():
    assert periode(date(2025, 11, 1), date(2026, 10, 31)) == "novembre 2025 à octobre 2026"


# --- Synthèse ---------------------------------------------------------------------

def test_synthese_met_le_montant_de_la_premiere_carte_en_ambre():
    phrase = phrase_synthese([resultat("a", "512.30"), resultat("b", "400")])
    assert "**Carte a**" in phrase
    assert f":orange[**512,30{S}\\$**]" in phrase
    assert phrase.count(":orange[") == 1  # seul élément ambre
    assert "actuelle" not in phrase


def test_synthese_donne_l_ecart_avec_la_carte_actuelle():
    phrase = phrase_synthese([resultat("a", "512.30"), resultat("b", "400")], "b")
    assert f"112,30{S}\\$ de plus par an" in phrase
    assert phrase.endswith("qu'avec ta carte actuelle, Carte b.")


def test_synthese_quand_la_carte_actuelle_est_deja_la_meilleure():
    phrase = phrase_synthese([resultat("a", "512.30"), resultat("b", "400")], "a")
    assert "déjà ta carte actuelle" in phrase


def test_synthese_quand_la_carte_actuelle_rapporte_autant():
    phrase = phrase_synthese([resultat("a", "100"), resultat("b", "100")], "b")
    assert "rapporte autant" in phrase


def test_synthese_refuse_une_carte_actuelle_inconnue():
    with pytest.raises(ValueError, match="inconnue"):
        phrase_synthese([resultat("a", "1")], "zzz")


# --- Classement et détail ---------------------------------------------------------

def test_classement_garde_l_ordre_et_formate_les_montants():
    lignes = lignes_classement([resultat("a", "300", frais="120"), resultat("b", "-5")])
    assert [l["Rang"] for l in lignes] == [1, 2]
    assert lignes[0]["Récompenses"] == f"420,00{S}$"
    assert lignes[0]["Frais annuels"] == f"120,00{S}$"
    assert lignes[1]["Valeur nette"] == f"-5,00{S}$"


def test_barres_en_nombres_dans_l_ordre_du_classement():
    assert barres_classement([resultat("a", "300.25"), resultat("b", "-5")]) == [
        {"Carte": "Carte a", "Valeur nette ($)": 300.25},
        {"Carte": "Carte b", "Valeur nette ($)": -5.0},
    ]


def test_valeur_du_point_affichee():
    assert valeur_du_point(carte()) == "remise en argent"
    assert valeur_du_point(carte(type_recompense="points", valeur_point="0.71")) \
        == f"0,71{S}¢ par point"


def test_detail_par_categorie_avec_rendement():
    r = resultat("a", "10", detail={
        "restaurants": DetailCategorie(D("100"), D("2.00")),
        "epicerie": DetailCategorie(D("400"), D("6.00")),
    })
    lignes = lignes_detail(r)
    assert [l["Catégorie"] for l in lignes] == ["Épicerie", "Restaurants"]  # plus grosse d'abord
    assert lignes[0]["Rendement"] == f"1,50{S}%"
    assert lignes[1]["Récompense"] == f"2,00{S}$"


def test_detail_d_une_categorie_a_depense_nulle():
    r = resultat("a", "0", detail={"epicerie": DetailCategorie(D("0"), D("0"))})
    assert lignes_detail(r)[0]["Rendement"] == f"0,00{S}%"


def test_notes_du_detail():
    r = resultat("a", "80", frais="120", choisies=("epicerie", "restaurants"),
                 plafonds=("manger_boire",))
    notes = notes_detail(r)
    assert notes[0] == f"Récompenses : 200,00{S}$ − frais annuels 120,00{S}$ = 80,00{S}$."
    assert any("Épicerie, Restaurants" in n for n in notes)
    assert any("manger_boire" in n for n in notes)


# --- Dépenses ---------------------------------------------------------------------

def test_repartition_avec_libelles_et_parts():
    jour = date(2026, 3, 1)
    lignes = lignes_repartition([
        Depense(jour, "X", D("75"), "epicerie"),
        Depense(jour, "Y", D("25"), "autres"),
    ])
    assert lignes == [
        {"Catégorie": "Épicerie", "Montant": f"75,00{S}$", "Part": f"75,00{S}%"},
        {"Catégorie": "Autre", "Montant": f"25,00{S}$", "Part": f"25,00{S}%"},
    ]


# --- Corrections ------------------------------------------------------------------

def test_marchands_a_corriger_restent_dans_la_liste_une_fois_corriges():
    transactions = lire_releve(releve_fictif_annuel())
    avant = marchands_a_corriger(transactions, {})
    assert [(m.marchand, m.nombre, m.total, m.categorie) for m in avant] == [
        ("QUINCAILLERIE BIDON", 12, D("1200.00"), "autres"),
        ("LIBRAIRIE IMAGINAIRE", 12, D("240.00"), "autres"),
    ]
    apres = marchands_a_corriger(transactions, {"LIBRAIRIE IMAGINAIRE": "divertissement"})
    assert [m.marchand for m in apres] == [m.marchand for m in avant]
    assert apres[1].categorie == "divertissement"


def test_marchands_a_corriger_limite_le_nombre():
    transactions = lire_releve(releve_fictif_annuel())
    assert len(marchands_a_corriger(transactions, {}, n=1)) == 1


def test_lignes_de_corrections_avec_libelle():
    lignes = lignes_corrections([MarchandACorriger("X", 2, D("10"), "epicerie")])
    assert lignes == [{"Marchand": "X", "Achats": 2, "Total": f"10,00{S}$",
                       COLONNE_CATEGORIE: "Épicerie"}]


MARCHANDS = [MarchandACorriger("A", 1, D("10"), "autres"),
             MarchandACorriger("B", 1, D("5"), "epicerie")]


def test_modification_ajoute_une_correction():
    assert appliquer_modifications({}, MARCHANDS, {0: {COLONNE_CATEGORIE: "Pharmacie"}}) \
        == {"A": "pharmacie"}


def test_revenir_a_autre_retire_la_correction():
    assert appliquer_modifications({"B": "epicerie"}, MARCHANDS,
                                   {1: {COLONNE_CATEGORIE: "Autre"}}) == {}
    # Cellule vidée : même effet
    assert appliquer_modifications({"B": "epicerie"}, MARCHANDS,
                                   {"1": {COLONNE_CATEGORIE: None}}) == {}


def test_modification_ne_change_pas_les_corrections_d_origine():
    origine = {"B": "epicerie"}
    appliquer_modifications(origine, MARCHANDS, {0: {COLONNE_CATEGORIE: "Pharmacie"}})
    assert origine == {"B": "epicerie"}


def test_modification_vers_un_libelle_inconnu_est_refusee():
    with pytest.raises(ValueError, match="inconnue"):
        appliquer_modifications({}, MARCHANDS, {0: {COLONNE_CATEGORIE: "Bidon"}})


def test_corrections_aller_retour_en_csv():
    corrections = {"Z MARCHAND, AVEC VIRGULE": "epicerie", "A MARCHAND": "restaurants"}
    contenu = corrections_en_csv(corrections)
    assert contenu.decode().splitlines()[:2] == ["marchand,categorie", "A MARCHAND,restaurants"]
    assert lire_corrections_csv(contenu) == corrections


def test_lecture_des_corrections_ignore_autre_et_le_bom():
    contenu = "﻿marchand,categorie\nA,autres\nB,epicerie\n".encode()
    assert lire_corrections_csv(contenu) == {"B": "epicerie"}


@pytest.mark.parametrize("contenu, message", [
    (b"nom,cat\nA,epicerie\n", "colonnes"),
    (b"marchand,categorie\nA,bidon\n", "ligne 2 : catégorie inconnue"),
    (b"marchand,categorie\n,epicerie\n", "marchand vide"),
    ("marchand,categorie\nÉ,epicerie\n".encode("cp1252"), "UTF-8"),
])
def test_corrections_illisibles_sont_refusees(contenu, message):
    with pytest.raises(ValueError, match=message):
        lire_corrections_csv(contenu)
