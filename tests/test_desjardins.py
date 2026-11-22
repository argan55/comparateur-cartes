"""Tests du lecteur de relevés CSV Desjardins (étape 1).

Tous les relevés utilisés ici sont fictifs (dossier tests/donnees/).
"""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from src.desjardins import Transaction, lire_releve

DONNEES = Path(__file__).parent / "donnees"


def lire_fichier_fictif(nom: str) -> list[Transaction]:
    # On passe des octets, comme le fera l'import Streamlit (rien n'est écrit sur disque).
    return lire_releve((DONNEES / nom).read_bytes())


# Une ligne de carte de crédit (13 colonnes) : achat en colonne 11, crédit en colonne 12.
def ligne_carte(date_txt="2026/03/01", description="MARCHAND FICTIF   MONTREAL   QC",
                achat="10.00", credit=""):
    achat = f'"{achat}"' if achat == "" else achat
    credit = f'"{credit}"' if credit == "" else credit
    return (f'Carte Fictive **** 0000,"","",{date_txt},00001,{description},'
            f'"","","","","",{achat},{credit}')


# --- Relevé de carte de crédit --------------------------------------------


def test_releve_carte_fictif_donne_six_transactions_triees_par_date():
    transactions = lire_fichier_fictif("releve_fictif_carte.csv")

    assert len(transactions) == 6
    dates = [t.date for t in transactions]
    # Le fichier Desjardins n'est pas trié : le lecteur trie du plus ancien au plus récent.
    assert dates == sorted(dates)
    assert dates[0] == date(2026, 1, 5)


def test_achat_de_carte_est_un_montant_positif():
    achat = lire_fichier_fictif("releve_fictif_carte.csv")[0]

    assert achat == Transaction(
        date=date(2026, 1, 5),
        description="EPICERIE DU QUARTIER MONTREAL QC",
        marchand="EPICERIE DU QUARTIER",
        montant=Decimal("87.45"),
        nature="achat",
        source="carte",
    )


def test_espaces_multiples_de_la_description_sont_reduits():
    # Desjardins aligne les descriptions de carte avec des espaces : on les réduit à un seul.
    transactions = lire_fichier_fictif("releve_fictif_carte.csv")

    assert all("  " not in t.description for t in transactions)
    assert transactions[0].description == "EPICERIE DU QUARTIER MONTREAL QC"


def test_marchand_est_pris_sur_les_25_premiers_caracteres_sans_la_ville():
    transactions = lire_fichier_fictif("releve_fictif_carte.csv")

    assert transactions[0].marchand == "EPICERIE DU QUARTIER"
    assert transactions[-1].marchand == "Transport Exemple"


def test_nom_de_marchand_tronque_qui_colle_a_la_ville_est_bien_separe():
    # Desjardins coupe les noms à 25 caractères : « …FICTIVE » + « LAVAL » devient « …FICTILAVAL ».
    resto = lire_fichier_fictif("releve_fictif_carte.csv")[1]

    assert resto.description == "RESTO LA FOURCHETTE FICTILAVAL QC"
    assert resto.marchand == "RESTO LA FOURCHETTE FICTI"


def test_marchand_d_un_releve_de_compte_est_la_description():
    achat_interac = lire_fichier_fictif("releve_fictif_compte.csv")[2]

    assert achat_interac.marchand == "Achat Interac, Boulangerie Fictive"


def test_paiement_de_la_carte_est_reconnu_et_negatif():
    paiement = next(t for t in lire_fichier_fictif("releve_fictif_carte.csv")
                    if t.nature == "paiement")

    assert paiement.montant == Decimal("-450.00")
    assert paiement.description == "PAIEMENT CAISSE"


def test_remise_de_la_carte_actuelle_est_reconnue():
    # La remise de la carte qu'on a déjà n'est pas une dépense : elle a sa propre nature.
    remise = next(t for t in lire_fichier_fictif("releve_fictif_carte.csv")
                  if t.nature == "remise")

    assert remise.montant == Decimal("-3.21")


def test_autre_credit_est_un_remboursement_de_marchand():
    remboursement = next(t for t in lire_fichier_fictif("releve_fictif_carte.csv")
                         if t.nature == "remboursement")

    assert remboursement.marchand == "LIBRAIRIE IMAGINAIRE"
    assert remboursement.montant == Decimal("-19.99")


def test_frais_de_credit_de_la_carte_ont_leur_propre_nature():
    # Intérêts et frais de la carte : dans la colonne des achats, mais ce n'est pas une dépense.
    frais = lire_releve(ligne_carte(description="FRAIS DE CREDIT", achat="2.15"))[0]

    assert frais.nature == "frais"
    assert frais.montant == Decimal("2.15")


def test_montant_de_plus_de_mille_dollars_est_lu_exactement():
    dernier = lire_fichier_fictif("releve_fictif_carte.csv")[-1]

    assert dernier.montant == Decimal("1234.50")
    assert isinstance(dernier.montant, Decimal)


def test_aucune_donnee_d_identification_n_est_conservee():
    # Ni le nom de la carte, ni le numéro masqué, ni la caisse, ni le folio.
    for nom in ("releve_fictif_carte.csv", "releve_fictif_compte.csv"):
        for t in lire_fichier_fictif(nom):
            texte = repr(t)
            assert "0000" not in texte
            assert "Fictive ****" not in texte
            assert "Caisse-Exemple" not in texte


# --- Relevé de compte (opérations) ------------------------------------------


def test_releve_compte_fictif_donne_retraits_positifs_et_depots_negatifs():
    transactions = lire_fichier_fictif("releve_fictif_compte.csv")

    assert [(t.nature, t.montant) for t in transactions] == [
        ("depot", Decimal("-2100.00")),
        ("retrait", Decimal("95.30")),
        ("retrait", Decimal("12.75")),
        ("retrait", Decimal("2500.00")),
    ]
    assert all(t.source == "compte" for t in transactions)


def test_virgule_dans_la_description_ne_decale_pas_les_colonnes():
    # Desjardins ne met pas la description entre guillemets : une virgule
    # dedans crée une colonne de trop. Le lecteur la recolle.
    achat_interac = lire_fichier_fictif("releve_fictif_compte.csv")[2]

    assert achat_interac.description == "Achat Interac, Boulangerie Fictive"
    assert achat_interac.montant == Decimal("12.75")
    assert achat_interac.nature == "retrait"


# --- Encodage et forme du fichier -------------------------------------------


def test_texte_et_octets_donnent_le_meme_resultat():
    contenu = (DONNEES / "releve_fictif_carte.csv").read_text(encoding="utf-8")

    assert lire_releve(contenu) == lire_fichier_fictif("releve_fictif_carte.csv")


def test_fichier_avec_bom_et_fins_de_ligne_windows_est_accepte():
    contenu = "﻿" + ligne_carte() + "\r\n" + ligne_carte(achat="5.00") + "\r\n"

    transactions = lire_releve(contenu.encode("utf-8"))

    assert [t.montant for t in transactions] == [Decimal("10.00"), Decimal("5.00")]


def test_fichier_en_windows_1252_avec_accents_est_accepte():
    contenu = ligne_carte(description="CAFÉ DE LA GARE   MONTRÉAL   QC")

    transaction = lire_releve(contenu.encode("cp1252"))[0]

    assert transaction.description == "CAFÉ DE LA GARE MONTRÉAL QC"


def test_lignes_vides_sont_ignorees():
    contenu = "\n" + ligne_carte() + "\n\n"

    assert len(lire_releve(contenu)) == 1


def test_montant_avec_espaces_autour_est_accepte():
    transaction = lire_releve(ligne_carte(achat=" 7.50 "))[0]

    assert transaction.montant == Decimal("7.50")


def test_montant_negatif_dans_la_colonne_achat_est_conserve_avec_son_signe():
    # Pas vu dans un vrai export, mais on ne doit pas perdre le signe s'il apparaît.
    transaction = lire_releve(ligne_carte(achat="-4.00"))[0]

    assert transaction.montant == Decimal("-4.00")


def test_montant_est_arrondi_au_cent():
    transaction = lire_releve(ligne_carte(achat="10.005"))[0]

    assert transaction.montant == Decimal("10.01")


# --- Fichiers refusés ---------------------------------------------------------


def test_fichier_vide_est_refuse():
    with pytest.raises(ValueError, match="vide"):
        lire_releve(b"")


def test_fichier_qui_n_est_pas_un_releve_desjardins_est_refuse():
    with pytest.raises(ValueError, match="format"):
        lire_releve("date,montant\n2026-01-01,10\n")


def test_date_illisible_est_refusee_avec_le_numero_de_ligne():
    contenu = ligne_carte() + "\n" + ligne_carte(date_txt="01/03/2026")

    with pytest.raises(ValueError, match="ligne 2.*date"):
        lire_releve(contenu)


def test_montant_illisible_est_refuse_avec_le_numero_de_ligne():
    with pytest.raises(ValueError, match="ligne 1.*montant"):
        lire_releve(ligne_carte(achat="dix"))


def test_ligne_sans_aucun_montant_est_refusee():
    with pytest.raises(ValueError, match="ligne 1.*aucun montant"):
        lire_releve(ligne_carte(achat="", credit=""))


def test_ligne_avec_achat_et_credit_a_la_fois_est_refusee():
    with pytest.raises(ValueError, match="ligne 1.*deux montants"):
        lire_releve(ligne_carte(achat="10.00", credit="10.00"))
