"""Tests de la lecture et de la validation des tables de cartes (étape 3)."""

from datetime import date
from decimal import Decimal

import pytest

from src.cartes import COLONNES_CARTES, COLONNES_TAUX, Taux, charger_cartes, lire_cartes

EN_TETE_CARTES = ",".join(COLONNES_CARTES)
EN_TETE_TAUX = ",".join(COLONNES_TAUX)

# Une carte fictive valide : on en modifie un champ à la fois pour tester les refus.
CARTE = {
    "id": "fictive", "nom": "Carte Fictive", "emetteur": "Banque Fictive", "reseau": "Visa",
    "type_recompense": "remise", "valeur_point_cents": "100", "frais_annuels": "0",
    "revenu_min": "", "frais_change_pct": "2.5", "nb_categories_au_choix": "",
    "source": "https://exemple.invalid/carte", "verifie_le": "2026-11-22", "notes": "",
}
TAUX = [
    {"carte_id": "fictive", "categorie": "epicerie", "taux_par_dollar": "0.03", "au_choix": "",
     "plafond_depenses": "500", "periode_plafond": "mois", "groupe_plafond": ""},
    {"carte_id": "fictive", "categorie": "autres", "taux_par_dollar": "0.005", "au_choix": "",
     "plafond_depenses": "", "periode_plafond": "", "groupe_plafond": ""},
]


def en_csv(en_tete: str, colonnes: list[str], lignes: list[dict]) -> str:
    return "\n".join([en_tete] + [",".join(l[c] for c in colonnes) for l in lignes])


def lire(cartes=None, taux=None):
    return lire_cartes(en_csv(EN_TETE_CARTES, COLONNES_CARTES, cartes or [CARTE]),
                       en_csv(EN_TETE_TAUX, COLONNES_TAUX, taux or TAUX))


def avec(base: dict, **changements) -> dict:
    return {**base, **changements}


# --- Vraies tables du dépôt ---------------------------------------------------------


def test_les_tables_du_depot_se_lisent_sans_erreur_et_comptent_5_a_10_cartes():
    cartes = charger_cartes()

    assert 5 <= len(cartes) <= 10
    assert all(c.source and c.verifie_le for c in cartes)


def test_tangerine_a_deux_categories_au_choix():
    tangerine = next(c for c in charger_cartes() if c.id == "tangerine_remises")

    assert tangerine.nb_categories_au_choix == 2
    assert sum(t.au_choix for t in tangerine.taux) == 7


# --- Carte fictive valide ------------------------------------------------------------


def test_carte_fictive_est_lue_avec_ses_taux():
    carte = lire()[0]

    assert carte.nom == "Carte Fictive"
    assert carte.frais_annuels == Decimal("0")
    assert carte.verifie_le == date(2026, 11, 22)
    assert carte.revenu_min is None
    assert carte.taux == (
        Taux("epicerie", Decimal("0.03"), False, Decimal("500"), "mois", "epicerie"),
        Taux("autres", Decimal("0.005")),
    )


def test_plafond_sans_groupe_forme_son_propre_groupe():
    epicerie = lire()[0].taux[0]

    assert epicerie.groupe_plafond == "epicerie"


# --- Refus --------------------------------------------------------------------------


def test_identifiant_en_double_est_refuse():
    with pytest.raises(ValueError, match="en double"):
        lire(cartes=[CARTE, CARTE])


def test_taux_pour_une_carte_inconnue_est_refuse():
    with pytest.raises(ValueError, match="ligne 2.*carte inconnue"):
        lire(taux=[avec(TAUX[0], carte_id="inexistante"), TAUX[1]])


def test_categorie_inconnue_est_refusee():
    with pytest.raises(ValueError, match="catégorie inconnue.*voyage"):
        lire(taux=[avec(TAUX[0], categorie="voyage"), TAUX[1]])


def test_carte_sans_taux_autres_est_refusee():
    with pytest.raises(ValueError, match="autres"):
        lire(taux=[TAUX[0]])


def test_categorie_en_double_pour_une_carte_est_refusee():
    with pytest.raises(ValueError, match="en double.*epicerie"):
        lire(taux=[TAUX[0], TAUX[0], TAUX[1]])


def test_plafond_sans_periode_est_refuse():
    with pytest.raises(ValueError, match="période"):
        lire(taux=[avec(TAUX[0], periode_plafond=""), TAUX[1]])


def test_periode_inconnue_est_refusee():
    with pytest.raises(ValueError, match="période inconnue"):
        lire(taux=[avec(TAUX[0], periode_plafond="semaine"), TAUX[1]])


def test_groupe_avec_deux_plafonds_differents_est_refuse():
    essence = avec(TAUX[0], categorie="essence", plafond_depenses="900", groupe_plafond="g")
    with pytest.raises(ValueError, match="plafonds différents"):
        lire(taux=[avec(TAUX[0], groupe_plafond="g"), essence, TAUX[1]])


def test_taux_au_choix_sans_nombre_de_choix_est_refuse():
    with pytest.raises(ValueError, match="nb_categories_au_choix"):
        lire(taux=[avec(TAUX[0], au_choix="oui"), TAUX[1]])


def test_nombre_de_choix_sans_taux_au_choix_est_refuse():
    with pytest.raises(ValueError, match="nb_categories_au_choix"):
        lire(cartes=[avec(CARTE, nb_categories_au_choix="2")])


def test_type_de_recompense_inconnu_est_refuse():
    with pytest.raises(ValueError, match="type de récompense"):
        lire(cartes=[avec(CARTE, type_recompense="miles")])


def test_source_vide_est_refusee():
    with pytest.raises(ValueError, match="source"):
        lire(cartes=[avec(CARTE, source="")])


def test_date_de_verification_illisible_est_refusee():
    with pytest.raises(ValueError, match="date de vérification"):
        lire(cartes=[avec(CARTE, verifie_le="22/11/2026")])


def test_frais_negatifs_sont_refuses():
    with pytest.raises(ValueError, match="frais_annuels"):
        lire(cartes=[avec(CARTE, frais_annuels="-5")])


def test_virgule_en_trop_dans_les_notes_est_signalee():
    with pytest.raises(ValueError, match="nombre de colonnes"):
        lire(cartes=[avec(CARTE, notes="plafond 500, puis 1 %")])


def test_colonne_manquante_est_signalee():
    with pytest.raises(ValueError, match="colonne.*manquante.*frais_annuels"):
        lire_cartes("id,nom\nx,y", en_csv(EN_TETE_TAUX, COLONNES_TAUX, TAUX))
