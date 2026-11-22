"""Valeur nette annuelle de chaque carte pour 12 mois de dépenses (étape 3).

valeur nette = récompenses (remises + points convertis en $) − frais annuels

- Taux applicable : celui de la catégorie, sinon celui de son parent, sinon « autres ».
- Plafond : on cumule les dépenses du groupe sur l'année ou par mois civil
  (approximation du relevé mensuel) ; la part au-delà du plafond gagne le taux
  « autres ». Dans un groupe de plusieurs catégories, la part plafonnée est
  répartie au prorata.
- Catégories au choix : on essaie toutes les combinaisons et on garde la meilleure.
- livraison_est_restaurant=False : la livraison de repas ne prend plus le taux
  restaurants ; sans taux propre, elle gagne le taux « autres ».
"""

from collections import defaultdict
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from itertools import combinations

from src.cartes import Carte, Taux
from src.categories import AUTRE, LIVRAISON, parents
from src.depenses import Depense

UN_CENT = Decimal("0.01")


@dataclass(frozen=True)
class DetailCategorie:
    depenses: Decimal
    recompense: Decimal  # en $, arrondie au cent


@dataclass(frozen=True)
class ResultatCarte:
    carte: Carte
    recompenses: Decimal  # somme des récompenses du détail
    frais: Decimal
    valeur_nette: Decimal
    detail: dict[str, DetailCategorie]  # par catégorie de dépense
    categories_choisies: tuple[str, ...]  # catégories au choix retenues (Tangerine)
    plafonds_atteints: tuple[str, ...]  # groupes dont le plafond a été dépassé au moins une fois


def classer(cartes: list[Carte], depenses: list[Depense],
            livraison_est_restaurant: bool = True) -> list[ResultatCarte]:
    """Toutes les cartes, de la meilleure valeur nette à la pire."""
    resultats = [calculer(carte, depenses, livraison_est_restaurant) for carte in cartes]
    return sorted(resultats, key=lambda r: (-r.valeur_nette, r.carte.nom))


def calculer(carte: Carte, depenses: list[Depense],
             livraison_est_restaurant: bool = True) -> ResultatCarte:
    au_choix = [t.categorie for t in carte.taux if t.au_choix]
    if au_choix:
        nombre = min(carte.nb_categories_au_choix, len(au_choix))
        possibilites = list(combinations(au_choix, nombre))
    else:
        possibilites = [()]

    # max garde la première combinaison en cas d'égalité (ordre de taux.csv).
    choisies, (detail, plafonds) = max(
        ((choix, _recompenser(carte, depenses, set(choix), livraison_est_restaurant)) for choix in possibilites),
        key=lambda element: sum(d.recompense for d in element[1][0].values()),
    )
    recompenses = sum((d.recompense for d in detail.values()), Decimal("0"))
    return ResultatCarte(
        carte=carte,
        recompenses=recompenses,
        frais=carte.frais_annuels,
        valeur_nette=recompenses - carte.frais_annuels,
        detail=detail,
        categories_choisies=tuple(choisies),
        plafonds_atteints=plafonds,
    )


def _recompenser(carte: Carte, depenses: list[Depense],
                 choisies: set[str],
                 livraison_est_restaurant: bool) -> tuple[dict[str, DetailCategorie], tuple[str, ...]]:
    actifs = {t.categorie: t for t in carte.taux if not t.au_choix or t.categorie in choisies}
    taux_autres = actifs[AUTRE]

    def taux_de(categorie: str) -> Taux:
        chaine = parents(categorie)
        if categorie == LIVRAISON and not livraison_est_restaurant:
            chaine = [categorie]
        for c in chaine:
            if c in actifs:
                return actifs[c]
        return taux_autres

    # 1er passage : dépense totale de chaque groupe plafonné, par période.
    lignes = []
    totaux: dict[tuple, Decimal] = defaultdict(Decimal)
    plafonds: dict[tuple, Decimal] = {}
    for d in depenses:
        t = taux_de(d.categorie)
        cle = None
        if t.plafond_depenses is not None:
            periode = (d.date.year, d.date.month) if t.periode_plafond == "mois" else "an"
            cle = (t.groupe_plafond, periode)
            totaux[cle] += d.montant
            plafonds[cle] = t.plafond_depenses
        lignes.append((d, t, cle))

    # Part de la dépense du groupe qui reste sous le plafond.
    sous_plafond = {
        cle: min(total, plafonds[cle]) / total if total > 0 else Decimal("1")
        for cle, total in totaux.items()
    }
    depasses = sorted({cle[0] for cle, total in totaux.items() if total > plafonds[cle]})

    # 2e passage : récompense de chaque dépense, en dollars.
    depense_par_cat: dict[str, Decimal] = defaultdict(Decimal)
    recompense_par_cat: dict[str, Decimal] = defaultdict(Decimal)
    for d, t, cle in lignes:
        part = sous_plafond[cle] if cle is not None else Decimal("1")
        taux_effectif = part * t.taux_par_dollar + (1 - part) * taux_autres.taux_par_dollar
        depense_par_cat[d.categorie] += d.montant
        recompense_par_cat[d.categorie] += d.montant * taux_effectif * carte.valeur_point_cents / 100

    detail = {
        cat: DetailCategorie(depense_par_cat[cat],
                             recompense_par_cat[cat].quantize(UN_CENT, rounding=ROUND_HALF_UP))
        for cat in depense_par_cat
    }
    return detail, tuple(depasses)
