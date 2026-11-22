"""Tests de la catégorisation par mots-clés de marchand (étape 2)."""

import csv
from pathlib import Path

import pytest

from src.categories import AUTRE, CATEGORIES, REGLES, categoriser, normaliser, parents

RACINE = Path(__file__).parent.parent


# --- Cohérence avec la table des taux ------------------------------------------


def test_toutes_les_categories_de_taux_csv_sont_connues():
    # L'étape 3 cherche les taux par ces clés : aucune ne doit manquer.
    with open(RACINE / "data" / "taux.csv", encoding="utf-8") as f:
        categories_des_taux = {ligne["categorie"] for ligne in csv.DictReader(f)}

    assert categories_des_taux <= set(CATEGORIES)


def test_la_categorie_autre_s_appelle_autres_comme_dans_taux_csv():
    assert AUTRE == "autres"
    assert CATEGORIES[AUTRE].libelle == "Autre"


def test_chaque_regle_mene_a_une_categorie_connue():
    assert all(categorie in CATEGORIES for categorie, _ in REGLES)


def test_chaque_parent_est_une_categorie_connue_sans_parent_lui_meme():
    for categorie in CATEGORIES.values():
        if categorie.parent is not None:
            assert categorie.parent in CATEGORIES
            assert CATEGORIES[categorie.parent].parent is None


def test_parents_donne_la_categorie_puis_son_parent():
    assert parents("epicerie_reseau_sobeys") == ["epicerie_reseau_sobeys", "epicerie"]
    assert parents("essence") == ["essence"]


# --- Normalisation ------------------------------------------------------------


def test_normaliser_met_en_majuscules_sans_accents_ni_ponctuation():
    assert normaliser("Café-Bistro l'Étoile*  #12") == "CAFE BISTRO L ETOILE 12"


def test_normaliser_garde_l_esperluette():
    assert normaliser("a&w") == "A&W"


# --- Une règle par famille de catégories -----------------------------------------


@pytest.mark.parametrize(
    ("marchand", "attendu"),
    [
        ("METRO PLUS ROSEMONT", "epicerie"),
        ("SUPER C #123", "epicerie"),
        ("MAXI & CIE 8888", "epicerie"),
        ("IGA EXTRA 9999", "epicerie_reseau_sobeys"),
        ("PHARMAPRIX 0001", "pharmacie_reseau_loblaw"),
        ("SHOPPERS DRUG MART #12", "pharmacie_reseau_loblaw"),
        ("JEAN COUTU 123", "pharmacie"),
        ("RESTAURANT CHEZ FICTIF", "restaurants"),
        ("TIM HORTONS #0001", "restaurants"),
        ("MCDONALD'S #400", "restaurants"),
        ("UBER CANADA/UBEREATS", "livraison_repas"),
        ("DOORDASH*RESTO FICTIF", "livraison_repas"),
        ("UBER CANADA/UBERTRIP", "covoiturage"),
        ("LYFT *RIDE", "covoiturage"),
        ("STM-STATION-FICTIVE", "transport_commun"),
        ("VIA RAIL CANADA", "transport_commun"),
        ("PETRO-CANADA 12345", "essence"),
        ("ULTRAMAR 001", "essence"),
        ("COSTCO GAS W123", "essence"),
        ("NETFLIX.COM", "abonnements_numeriques"),
        ("SPOTIFY P0123", "abonnements_numeriques"),
        ("APPLE.COM/BILL", "abonnements_numeriques"),
        ("HYDRO-QUEBEC", "paiements_recurrents"),
        ("VIDEOTRON LTEE", "paiements_recurrents"),
        ("CINEPLEX ODEON 9999", "divertissement_cineplex"),
        ("TICKETMASTER CANADA", "divertissement"),
        # Ajouts après lecture des marchands non reconnus (chaînes et mots génériques seulement)
        ("MCDONALDS 1234", "restaurants"),
        ("McDonalds 99999", "restaurants"),
        ("LA BELLE PROVINCE", "restaurants"),
        ("*3 BRASSEURS", "restaurants"),
        ("*WENDY'S", "restaurants"),
        ("DAIRY QUEEN LAVAL", "restaurants"),
        ("KRISPY KREME #000", "restaurants"),
        ("*TST*RESTO FICTIF", "restaurants"),  # Toast : terminal de paiement de restaurants
        ("CHEZ FICTIF DELI INC", "restaurants"),
        ("BAGELS FICTIFS", "restaurants"),
        ("CASSE-CROUTE FICTIF TACOS", "restaurants"),
        ("FICTIF DONER", "restaurants"),
        ("*FICTIF GRILL", "restaurants"),
        ("CREMERIE FICTIVE", "restaurants"),
        ("ALIMENTATION FICTIVE", "epicerie"),
        ("CINE STARZ FICTIF", "divertissement"),
        ("PAYPAL *NORTON", "abonnements_numeriques"),
        # Choix validés : Too Good To Go → restaurants ; jeux vidéo → divertissement
        ("TGTG abc123xyz", "restaurants"),
        ("TOO GOOD TO GO", "restaurants"),
        ("PAYPAL *STEAM GAMES", "divertissement"),
        ("STEAMGAMES.COM 0000000", "divertissement"),
        ("*Instant Gaming", "divertissement"),
    ],
)
def test_marchand_connu_est_bien_categorise(marchand, attendu):
    assert categoriser(marchand) == attendu


# --- Cas limites --------------------------------------------------------------------


def test_marchand_inconnu_va_dans_autre():
    assert categoriser("QUINCAILLERIE IMAGINAIRE") == AUTRE


def test_costco_hors_essence_reste_dans_autre():
    # Les entrepôts ne comptent pas comme épicerie pour la plupart des cartes.
    assert categoriser("COSTCO WHOLESALE W123") == AUTRE


def test_la_belle_province_n_est_pas_bell():
    # « BELLE » ne doit pas déclencher le mot-clé « BELL » (paiements récurrents).
    assert categoriser("LA BELLE PROVINCE") == "restaurants"


def test_un_mot_cle_doit_etre_un_mot_entier():
    assert categoriser("BARBIER FICTIF") == AUTRE  # pas « BAR »
    assert categoriser("CIGARES DU COIN") == AUTRE  # pas « IGA »
    assert categoriser("METROPOLIS BILLETS") == AUTRE  # pas « METRO »


def test_accents_et_minuscules_n_empechent_pas_la_reconnaissance():
    assert categoriser("Pétro-Canada") == "essence"
    assert categoriser("Hydro-Québec") == "paiements_recurrents"


def test_description_vide_va_dans_autre():
    assert categoriser("") == AUTRE
