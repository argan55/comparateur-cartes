"""Tests du calcul de la valeur nette annuelle par carte (étape 3).

Les montants attendus sont calculés à la main dans les commentaires.
"""

from datetime import date
from decimal import Decimal

from src.calcul import calculer, classer
from src.cartes import Carte, Taux
from src.depenses import Depense

D = Decimal


def carte(*taux, frais="0", type_recompense="remise", valeur_point="100", nb_choix=None, id="c"):
    return Carte(id=id, nom=f"Carte {id}", type_recompense=type_recompense,
                 valeur_point_cents=D(valeur_point), frais_annuels=D(frais),
                 taux=tuple(taux), nb_categories_au_choix=nb_choix)


def autres(taux="0.005"):
    return Taux("autres", D(taux))


def depense(categorie, montant, jour=date(2026, 3, 1), marchand="MARCHAND FICTIF"):
    return Depense(jour, marchand, D(montant), categorie)


# --- Remises et points ------------------------------------------------------------


def test_remise_simple_par_categorie():
    # 100 $ × 3 % + 50 $ × 0,5 % = 3,00 + 0,25 = 3,25 $
    c = carte(Taux("epicerie", D("0.03")), autres())

    resultat = calculer(c, [depense("epicerie", "100"), depense("autres", "50")])

    assert resultat.recompenses == D("3.25")
    assert resultat.valeur_nette == D("3.25")


def test_points_convertis_avec_la_valeur_fixe_du_point():
    # 1 000 $ × 1 point/$ × 0,71 ¢ = 7,10 $
    c = carte(Taux("autres", D("1")), type_recompense="points", valeur_point="0.71")

    assert calculer(c, [depense("autres", "1000")]).recompenses == D("7.10")


def test_frais_annuels_sont_soustraits_et_la_valeur_peut_etre_negative():
    # 1 000 $ × 1 % = 10 $ ; 10 − 120 = −110 $
    c = carte(autres("0.01"), frais="120")

    resultat = calculer(c, [depense("autres", "1000")])

    assert resultat.frais == D("120")
    assert resultat.valeur_nette == D("-110.00")


def test_sans_depense_la_valeur_nette_est_moins_les_frais():
    assert calculer(carte(autres(), frais="50"), []).valeur_nette == D("-50")


def test_remboursement_reduit_la_recompense():
    # (100 − 20) $ × 3 % = 2,40 $
    c = carte(Taux("epicerie", D("0.03")), autres())

    resultat = calculer(c, [depense("epicerie", "100"), depense("epicerie", "-20")])

    assert resultat.recompenses == D("2.40")
    assert resultat.detail["epicerie"].depenses == D("80")


# --- Catégorie, parent, « autres » ------------------------------------------------------


def test_categorie_sans_taux_gagne_le_taux_autres():
    # Essence sans taux propre : 200 $ × 0,5 % = 1,00 $
    c = carte(Taux("epicerie", D("0.03")), autres())

    assert calculer(c, [depense("essence", "200")]).recompenses == D("1.00")


def test_sous_categorie_de_reseau_prend_le_taux_du_parent():
    # IGA sur une carte qui n'a qu'un taux épicerie : 100 $ × 2 % = 2,00 $
    c = carte(Taux("epicerie", D("0.02")), autres())

    assert calculer(c, [depense("epicerie_reseau_sobeys", "100")]).recompenses == D("2.00")


def test_taux_propre_de_la_sous_categorie_l_emporte():
    # Scene+ : IGA à 2 points/$, épicerie ordinaire à 1 point/$ (taux « autres »), 1 ¢ le point
    c = carte(Taux("epicerie_reseau_sobeys", D("2")), Taux("autres", D("1")),
              type_recompense="points", valeur_point="1")

    resultat = calculer(c, [depense("epicerie_reseau_sobeys", "100"), depense("epicerie", "100")])

    assert resultat.recompenses == D("3.00")  # 2,00 + 1,00


def test_livraison_de_repas_prend_le_taux_restaurants():
    c = carte(Taux("restaurants", D("0.02")), autres())

    assert calculer(c, [depense("livraison_repas", "50")]).recompenses == D("1.00")


def test_livraison_hors_restaurants_prend_le_taux_autres():
    c = carte(Taux("restaurants", D("0.02")), autres())

    resultat = calculer(c, [depense("livraison_repas", "50")], livraison_est_restaurant=False)

    assert resultat.recompenses == D("0.25")  # 50 × 0,5 %


def test_livraison_hors_restaurants_garde_un_taux_propre_a_la_livraison():
    c = carte(Taux("restaurants", D("0.02")), Taux("livraison_repas", D("0.05")), autres())

    resultat = calculer(c, [depense("livraison_repas", "50")], livraison_est_restaurant=False)

    assert resultat.recompenses == D("2.50")


def test_option_livraison_ne_touche_pas_les_autres_sous_categories():
    c = carte(Taux("epicerie", D("0.02")), autres())

    resultat = calculer(c, [depense("epicerie_reseau_sobeys", "100")], livraison_est_restaurant=False)

    assert resultat.recompenses == D("2.00")


def test_classer_transmet_l_option_livraison():
    c1 = carte(Taux("restaurants", D("0.02")), autres(), id="resto")
    c2 = carte(Taux("autres", D("0.01")), id="plate")
    depenses = [depense("livraison_repas", "100")]

    assert classer([c1, c2], depenses)[0].carte.id == "resto"  # 2,00 contre 1,00
    assert classer([c1, c2], depenses, livraison_est_restaurant=False)[0].carte.id == "plate"


def test_detail_est_donne_par_categorie_de_depense():
    c = carte(Taux("epicerie", D("0.02")), autres())

    detail = calculer(c, [depense("epicerie_reseau_sobeys", "100"), depense("autres", "10")]).detail

    assert detail["epicerie_reseau_sobeys"].recompense == D("2.00")
    assert detail["autres"].recompense == D("0.05")


# --- Plafonds -------------------------------------------------------------------------


def test_plafond_annuel_le_surplus_gagne_le_taux_autres():
    # 3 600 $ × 2 % + 400 $ × 0,5 % = 72,00 + 2,00 = 74,00 $
    c = carte(Taux("restaurants", D("0.02"), plafond_depenses=D("3600"), periode_plafond="an",
                   groupe_plafond="restaurants"), autres())

    resultat = calculer(c, [depense("restaurants", "4000")])

    assert resultat.recompenses == D("74.00")
    assert resultat.plafonds_atteints == ("restaurants",)


def test_plafond_annuel_non_atteint():
    c = carte(Taux("restaurants", D("0.02"), plafond_depenses=D("3600"), periode_plafond="an",
                   groupe_plafond="restaurants"), autres())

    resultat = calculer(c, [depense("restaurants", "1000")])

    assert resultat.recompenses == D("20.00")
    assert resultat.plafonds_atteints == ()


def test_plafond_mensuel_est_compte_mois_par_mois():
    # Janvier : 500 $ × 3 % + 100 $ × 0,5 % = 15,50 $ ; février : 200 $ × 3 % = 6,00 $ → 21,50 $
    c = carte(Taux("epicerie", D("0.03"), plafond_depenses=D("500"), periode_plafond="mois",
                   groupe_plafond="epicerie"), autres())

    resultat = calculer(c, [depense("epicerie", "350", date(2026, 1, 3)),
                            depense("epicerie", "250", date(2026, 1, 20)),
                            depense("epicerie", "200", date(2026, 2, 5))])

    assert resultat.recompenses == D("21.50")


def test_plafond_partage_entre_deux_categories_du_meme_groupe():
    # Épicerie 800 $ + essence 400 $ = 1 200 $ pour un plafond commun de 1 000 $.
    # 1 000 $ × 2 % + 200 $ × 1,25 % = 20,00 + 2,50 = 22,50 $, réparti au prorata :
    # épicerie 2/3 → 15,00 $ ; essence 1/3 → 7,50 $
    plafond = dict(plafond_depenses=D("1000"), periode_plafond="an", groupe_plafond="epicerie_essence")
    c = carte(Taux("epicerie", D("0.02"), **plafond), Taux("essence", D("0.02"), **plafond),
              autres("0.0125"))

    resultat = calculer(c, [depense("epicerie", "800"), depense("essence", "400")])

    assert resultat.recompenses == D("22.50")
    assert resultat.detail["epicerie"].recompense == D("15.00")
    assert resultat.detail["essence"].recompense == D("7.50")


def test_sous_categorie_compte_dans_le_plafond_de_son_parent():
    # IGA (parent épicerie) et épicerie partagent le plafond mensuel de 500 $.
    # 500 $ × 3 % + 100 $ × 0,5 % = 15,50 $
    c = carte(Taux("epicerie", D("0.03"), plafond_depenses=D("500"), periode_plafond="mois",
                   groupe_plafond="epicerie"), autres())

    resultat = calculer(c, [depense("epicerie", "300"), depense("epicerie_reseau_sobeys", "300")])

    assert resultat.recompenses == D("15.50")


# --- Catégories au choix ---------------------------------------------------------------


def tangerine_fictive():
    return carte(Taux("epicerie", D("0.02"), au_choix=True),
                 Taux("restaurants", D("0.02"), au_choix=True),
                 Taux("essence", D("0.02"), au_choix=True),
                 autres(), nb_choix=2)


def test_les_meilleures_categories_au_choix_sont_retenues():
    # Choix optimal : restaurants (300 $) + essence (200 $) → 500 $ × 2 % + 100 $ × 0,5 % = 10,50 $
    resultat = calculer(tangerine_fictive(), [depense("epicerie", "100"),
                                              depense("restaurants", "300"),
                                              depense("essence", "200")])

    assert resultat.categories_choisies == ("restaurants", "essence")
    assert resultat.recompenses == D("10.50")


def test_categorie_au_choix_non_retenue_gagne_le_taux_autres():
    resultat = calculer(tangerine_fictive(), [depense("epicerie", "100"),
                                              depense("restaurants", "300"),
                                              depense("essence", "200")])

    assert resultat.detail["epicerie"].recompense == D("0.50")


def test_carte_sans_choix_n_a_aucune_categorie_choisie():
    assert calculer(carte(autres()), [depense("autres", "10")]).categories_choisies == ()


# --- Arrondis et classement -----------------------------------------------------------


def test_total_est_la_somme_des_details_arrondis_au_cent():
    # 3 × (0,10 $ × 0,5 % = 0,0005 $) : chaque détail est arrondi au cent séparément.
    c = carte(Taux("epicerie", D("0.005")), Taux("essence", D("0.005")), autres())

    resultat = calculer(c, [depense("epicerie", "1"), depense("essence", "1"), depense("autres", "1")])

    assert resultat.recompenses == sum(d.recompense for d in resultat.detail.values())
    assert resultat.recompenses == D("0.03")  # 3 × 0,005 $ arrondi à 0,01 $


def test_classement_de_la_meilleure_valeur_nette_a_la_pire():
    a = carte(autres("0.01"), id="a")  # 10 $
    b = carte(autres("0.02"), frais="5", id="b")  # 20 − 5 = 15 $
    c = carte(autres("0.005"), id="c")  # 5 $

    classement = classer([a, b, c], [depense("autres", "1000")])

    assert [r.carte.id for r in classement] == ["b", "a", "c"]
    assert [r.valeur_nette for r in classement] == [D("15.00"), D("10.00"), D("5.00")]
