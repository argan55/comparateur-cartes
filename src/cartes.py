"""Table des cartes de crédit : lecture et validation de data/cartes.csv et data/taux.csv (étape 3).

Une seule formule pour les remises et les points :
    valeur en $ = dépense × taux_par_dollar × valeur_point_cents / 100
- carte à remise : valeur_point_cents = 100 et taux_par_dollar = 0.02 pour 2 % ;
- carte à points : taux_par_dollar = points par dollar, valeur_point_cents = valeur fixe d'un point.

revenu_min et frais_change_pct sont lus pour être affichés, mais n'entrent pas
dans le calcul en v1 (conditions de revenu et achats en devises hors v1).
"""

import csv
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from src.categories import AUTRE, CATEGORIES

DOSSIER_DATA = Path(__file__).parent.parent / "data"
TYPES_RECOMPENSE = {"remise", "points"}
PERIODES = {"an", "mois"}

COLONNES_CARTES = [
    "id", "nom", "emetteur", "reseau", "type_recompense", "valeur_point_cents",
    "frais_annuels", "revenu_min", "frais_change_pct", "nb_categories_au_choix",
    "source", "verifie_le", "notes",
]
COLONNES_TAUX = [
    "carte_id", "categorie", "taux_par_dollar", "au_choix", "plafond_depenses",
    "periode_plafond", "groupe_plafond",
]


@dataclass(frozen=True)
class Taux:
    categorie: str
    taux_par_dollar: Decimal
    au_choix: bool = False
    plafond_depenses: Decimal | None = None  # au-delà, la dépense gagne le taux « autres »
    periode_plafond: str | None = None  # « an » ou « mois »
    groupe_plafond: str | None = None  # catégories qui partagent le même plafond


@dataclass(frozen=True)
class Carte:
    id: str
    nom: str
    type_recompense: str
    valeur_point_cents: Decimal
    frais_annuels: Decimal
    taux: tuple[Taux, ...]
    emetteur: str = ""
    reseau: str = ""
    nb_categories_au_choix: int | None = None
    revenu_min: Decimal | None = None
    frais_change_pct: Decimal | None = None
    source: str = ""
    verifie_le: date | None = None
    notes: str = ""


def charger_cartes(dossier: Path = DOSSIER_DATA) -> list[Carte]:
    """Lit data/cartes.csv et data/taux.csv."""
    return lire_cartes((dossier / "cartes.csv").read_text(encoding="utf-8-sig"),
                       (dossier / "taux.csv").read_text(encoding="utf-8-sig"))


def lire_cartes(texte_cartes: str, texte_taux: str) -> list[Carte]:
    lignes_cartes = _lire_table(texte_cartes, COLONNES_CARTES, "cartes.csv")
    lignes_taux = _lire_table(texte_taux, COLONNES_TAUX, "taux.csv")

    taux_par_carte: dict[str, list[Taux]] = {}
    for numero, ligne in lignes_cartes:
        if ligne["id"] in taux_par_carte:
            raise ValueError(f"cartes.csv, ligne {numero} : identifiant « {ligne['id']} » en double.")
        taux_par_carte[ligne["id"]] = []
    for numero, ligne in lignes_taux:
        if ligne["carte_id"] not in taux_par_carte:
            raise ValueError(f"taux.csv, ligne {numero} : carte inconnue « {ligne['carte_id']} ».")
        taux_par_carte[ligne["carte_id"]].append(_lire_taux(numero, ligne))

    return [_lire_carte(numero, ligne, taux_par_carte[ligne["id"]])
            for numero, ligne in lignes_cartes]


def _lire_table(texte: str, colonnes: list[str], nom: str) -> list[tuple[int, dict[str, str]]]:
    lecteur = csv.DictReader(texte.splitlines())
    manquantes = [c for c in colonnes if c not in (lecteur.fieldnames or [])]
    if manquantes:
        raise ValueError(f"{nom} : colonne(s) manquante(s) : {', '.join(manquantes)}.")
    lignes = []
    for numero, ligne in enumerate(lecteur, start=2):  # ligne 1 = en-tête
        if None in ligne or None in ligne.values():
            raise ValueError(f"{nom}, ligne {numero} : nombre de colonnes incorrect "
                             "(une virgule dans les notes ?).")
        lignes.append((numero, {cle: valeur.strip() for cle, valeur in ligne.items()}))
    return lignes


def _nombre(valeur: str, champ: str, ou: str, obligatoire: bool = True) -> Decimal | None:
    if not valeur:
        if obligatoire:
            raise ValueError(f"{ou} : « {champ} » est vide.")
        return None
    try:
        nombre = Decimal(valeur)
    except InvalidOperation:
        nombre = None
    if nombre is None or not nombre.is_finite() or nombre < 0:
        raise ValueError(f"{ou} : « {champ} » illisible ou négatif (« {valeur} »).")
    return nombre


def _lire_taux(numero: int, ligne: dict[str, str]) -> Taux:
    ou = f"taux.csv, ligne {numero}"
    categorie = ligne["categorie"]
    if categorie not in CATEGORIES:
        raise ValueError(f"{ou} : catégorie inconnue « {categorie} ».")
    if ligne["au_choix"] not in ("", "oui"):
        raise ValueError(f"{ou} : « au_choix » doit être vide ou « oui ».")
    plafond = _nombre(ligne["plafond_depenses"], "plafond_depenses", ou, obligatoire=False)
    periode = ligne["periode_plafond"] or None
    if (plafond is None) != (periode is None):
        raise ValueError(f"{ou} : un plafond demande une période (« an » ou « mois »), et inversement.")
    if periode is not None and periode not in PERIODES:
        raise ValueError(f"{ou} : période inconnue « {periode} » (« an » ou « mois »).")
    if categorie == AUTRE and (plafond is not None or ligne["au_choix"]):
        raise ValueError(f"{ou} : le taux « autres » ne peut être ni plafonné ni au choix.")
    return Taux(
        categorie=categorie,
        taux_par_dollar=_nombre(ligne["taux_par_dollar"], "taux_par_dollar", ou),
        au_choix=ligne["au_choix"] == "oui",
        plafond_depenses=plafond,
        periode_plafond=periode,
        # Un plafond sans groupe ne concerne que sa propre catégorie.
        groupe_plafond=(ligne["groupe_plafond"] or categorie) if plafond is not None else None,
    )


def _lire_carte(numero: int, ligne: dict[str, str], taux: list[Taux]) -> Carte:
    ou = f"cartes.csv, ligne {numero} ({ligne['id']})"
    if ligne["type_recompense"] not in TYPES_RECOMPENSE:
        raise ValueError(f"{ou} : type de récompense inconnu « {ligne['type_recompense']} ».")
    if not ligne["source"]:
        raise ValueError(f"{ou} : la source des conditions est obligatoire.")
    try:
        verifie_le = date.fromisoformat(ligne["verifie_le"])
    except ValueError:
        raise ValueError(f"{ou} : date de vérification illisible (attendu AAAA-MM-JJ).") from None

    categories = [t.categorie for t in taux]
    doublons = {c for c in categories if categories.count(c) > 1}
    if doublons:
        raise ValueError(f"{ou} : catégorie en double dans taux.csv : {', '.join(sorted(doublons))}.")
    if AUTRE not in categories:
        raise ValueError(f"{ou} : il manque le taux « autres » dans taux.csv.")

    plafonds_des_groupes: dict[str, tuple] = {}
    for t in taux:
        if t.groupe_plafond is not None:
            plafond = (t.plafond_depenses, t.periode_plafond)
            if plafonds_des_groupes.setdefault(t.groupe_plafond, plafond) != plafond:
                raise ValueError(f"{ou} : le groupe « {t.groupe_plafond} » a des plafonds différents.")

    nb_au_choix = _nombre(ligne["nb_categories_au_choix"], "nb_categories_au_choix", ou,
                          obligatoire=False)
    a_des_choix = any(t.au_choix for t in taux)
    if a_des_choix != (nb_au_choix is not None):
        raise ValueError(f"{ou} : « nb_categories_au_choix » doit être rempli si et seulement si "
                         "des taux sont au choix.")
    if nb_au_choix is not None and (nb_au_choix != int(nb_au_choix) or nb_au_choix < 1):
        raise ValueError(f"{ou} : « nb_categories_au_choix » doit être un entier positif.")

    return Carte(
        id=ligne["id"],
        nom=ligne["nom"],
        emetteur=ligne["emetteur"],
        reseau=ligne["reseau"],
        type_recompense=ligne["type_recompense"],
        valeur_point_cents=_nombre(ligne["valeur_point_cents"], "valeur_point_cents", ou),
        frais_annuels=_nombre(ligne["frais_annuels"], "frais_annuels", ou),
        revenu_min=_nombre(ligne["revenu_min"], "revenu_min", ou, obligatoire=False),
        frais_change_pct=_nombre(ligne["frais_change_pct"], "frais_change_pct", ou, obligatoire=False),
        nb_categories_au_choix=int(nb_au_choix) if nb_au_choix is not None else None,
        source=ligne["source"],
        verifie_le=verifie_le,
        notes=ligne["notes"],
        taux=tuple(taux),
    )
