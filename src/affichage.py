"""Mise en forme des résultats pour l'interface (étape 4).

Tout ce que app.py affiche est préparé ici : textes, lignes de tableaux,
corrections de catégories. app.py ne fait que poser ces éléments à l'écran.
"""

import csv
import io
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from src.calcul import ResultatCarte
from src.cartes import Carte
from src.categories import AUTRE, CATEGORIES
from src.depenses import Depense, marchands_non_reconnus, preparer_depenses
from src.desjardins import Transaction

ESPACE = " "  # espace insécable : « 1 234,50 $ » ne se coupe pas en fin de ligne
UN_CENT = Decimal("0.01")
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre"]

LIBELLES: dict[str, str] = {cle: c.libelle for cle, c in CATEGORIES.items()}
_CLES_PAR_LIBELLE = {libelle: cle for cle, libelle in LIBELLES.items()}

COLONNE_CATEGORIE = "Catégorie"  # colonne modifiable du tableau des corrections


# --- Nombres et dates -------------------------------------------------------------

def _decimal_fr(valeur: Decimal, decimales: int = 2) -> str:
    """« -1 234,50 » : espace insécable entre les milliers, virgule décimale."""
    arrondi = valeur.quantize(Decimal(1).scaleb(-decimales), rounding=ROUND_HALF_UP)
    signe = "-" if arrondi < 0 else ""
    texte = f"{abs(arrondi):,.{decimales}f}"  # « 1,234.50 »
    return signe + texte.replace(",", ESPACE).replace(".", ",")


def formater_montant(montant: Decimal) -> str:
    """1234.5 → « 1 234,50 $ »."""
    return f"{_decimal_fr(montant)}{ESPACE}$"


def formater_pct(part: Decimal) -> str:
    """0.0125 → « 1,25 % »."""
    return f"{_decimal_fr(part * 100)}{ESPACE}%"


def formater_cents(cents: Decimal) -> str:
    """0.71 → « 0,71 ¢ »."""
    return f"{_decimal_fr(cents)}{ESPACE}¢"


def pour_markdown(texte: str) -> str:
    """Streamlit lit « $…$ » comme une formule mathématique : on échappe les $."""
    return texte.replace("$", "\\$")


def periode(debut: date, fin: date) -> str:
    """« novembre 2025 à octobre 2026 »."""
    return f"{MOIS[debut.month - 1]} {debut.year} à {MOIS[fin.month - 1]} {fin.year}"


# --- Synthèse et classement -------------------------------------------------------

def phrase_synthese(resultats: list[ResultatCarte], id_actuelle: str | None = None) -> str:
    """Phrase en Markdown ; le montant de la 1re carte est le seul élément en ambre.

    resultats : déjà classés (src.calcul.classer).
    id_actuelle : la carte que la personne utilise, pour donner l'écart.
    """
    if not resultats:
        raise ValueError("Aucune carte à classer.")
    premiere = resultats[0]
    montant = pour_markdown(formater_montant(premiere.valeur_nette))
    phrase = (f"La carte la plus payante pour tes dépenses est **{premiere.carte.nom}** : "
              f":orange[**{montant}**] par an, frais annuels déduits.")
    if not id_actuelle:
        return phrase

    actuelle = next((r for r in resultats if r.carte.id == id_actuelle), None)
    if actuelle is None:
        raise ValueError(f"Carte actuelle inconnue « {id_actuelle} ».")
    if actuelle is premiere:
        return phrase + " C'est déjà ta carte actuelle."
    ecart = premiere.valeur_nette - actuelle.valeur_nette
    if ecart == 0:
        return phrase + f" Ta carte actuelle, {actuelle.carte.nom}, rapporte autant."
    return phrase + (f" C'est {pour_markdown(formater_montant(ecart))} de plus par an "
                     f"qu'avec ta carte actuelle, {actuelle.carte.nom}.")


def valeur_du_point(carte: Carte) -> str:
    if carte.type_recompense == "remise":
        return "remise en argent"
    return f"{formater_cents(carte.valeur_point_cents)} par point"


def barres_classement(resultats: list[ResultatCarte]) -> list[dict]:
    """Données du graphique : valeur nette en nombre (float), dans l'ordre du classement."""
    return [{"Carte": r.carte.nom, "Valeur nette ($)": float(r.valeur_nette)} for r in resultats]


def lignes_classement(resultats: list[ResultatCarte]) -> list[dict]:
    return [
        {
            "Rang": rang,
            "Carte": r.carte.nom,
            "Récompenses": formater_montant(r.recompenses),
            "Frais annuels": formater_montant(r.frais),
            "Valeur nette": formater_montant(r.valeur_nette),
        }
        for rang, r in enumerate(resultats, start=1)
    ]


def lignes_detail(resultat: ResultatCarte) -> list[dict]:
    """Une ligne par catégorie de dépense, la plus grosse dépense d'abord.

    Le rendement est la récompense en $ divisée par la dépense : il tient compte
    de la valeur du point et des plafonds.
    """
    lignes = []
    for cle, d in sorted(resultat.detail.items(), key=lambda item: item[1].depenses, reverse=True):
        rendement = d.recompense / d.depenses if d.depenses > 0 else Decimal("0")
        lignes.append({
            "Catégorie": LIBELLES[cle],
            "Dépenses": formater_montant(d.depenses),
            "Rendement": formater_pct(rendement),
            "Récompense": formater_montant(d.recompense),
        })
    return lignes


def notes_detail(resultat: ResultatCarte) -> list[str]:
    """Lignes de texte sous le détail : total, frais, choix et plafonds."""
    notes = [
        f"Récompenses : {formater_montant(resultat.recompenses)} − frais annuels "
        f"{formater_montant(resultat.frais)} = {formater_montant(resultat.valeur_nette)}.",
        f"Valeur retenue : {valeur_du_point(resultat.carte)}.",
    ]
    if resultat.categories_choisies:
        choisies = ", ".join(LIBELLES[c] for c in resultat.categories_choisies)
        notes.append(f"Catégories au choix retenues (les plus payantes) : {choisies}.")
    if resultat.plafonds_atteints:
        notes.append("Plafond dépassé (le surplus gagne le taux de base) : "
                     f"{', '.join(resultat.plafonds_atteints)}.")
    return notes


# --- Dépenses ---------------------------------------------------------------------

def lignes_repartition(depenses: list[Depense]) -> list[dict]:
    """Total par catégorie, la plus grosse d'abord, avec sa part du total."""
    totaux: dict[str, Decimal] = {}
    for d in depenses:
        totaux[d.categorie] = totaux.get(d.categorie, Decimal("0")) + d.montant
    total = sum(totaux.values(), Decimal("0"))
    return [
        {
            "Catégorie": LIBELLES[cle],
            "Montant": formater_montant(montant),
            "Part": formater_pct(montant / total) if total > 0 else "—",
        }
        for cle, montant in sorted(totaux.items(), key=lambda item: item[1], reverse=True)
    ]


def total_depenses(depenses: list[Depense]) -> Decimal:
    return sum((d.montant for d in depenses), Decimal("0"))


# --- Corrections des catégories ---------------------------------------------------

@dataclass(frozen=True)
class MarchandACorriger:
    marchand: str
    nombre: int
    total: Decimal
    categorie: str  # clé : la correction choisie, sinon AUTRE


def marchands_a_corriger(transactions: list[Transaction], corrections: dict[str, str],
                         n: int = 20) -> list[MarchandACorriger]:
    """Les n marchands non reconnus par les règles qui coûtent le plus.

    La liste ne dépend que des règles, pas des corrections : un marchand corrigé
    reste à sa place, ce qui permet de revenir sur un choix.
    """
    non_reconnus = marchands_non_reconnus(preparer_depenses(transactions))
    return [MarchandACorriger(m, nombre, total, corrections.get(m, AUTRE))
            for m, nombre, total in non_reconnus[:n]]


def lignes_corrections(marchands: list[MarchandACorriger]) -> list[dict]:
    return [
        {
            "Marchand": m.marchand,
            "Achats": m.nombre,
            "Total": formater_montant(m.total),
            COLONNE_CATEGORIE: LIBELLES[m.categorie],
        }
        for m in marchands
    ]


def appliquer_modifications(corrections: dict[str, str], marchands: list[MarchandACorriger],
                            lignes_modifiees: dict) -> dict[str, str]:
    """Nouvelles corrections après une modification du tableau.

    lignes_modifiees : {numéro de ligne: {colonne: nouvelle valeur}}, comme le
    « edited_rows » de st.data_editor. Revenir à « Autre » retire la correction.
    """
    nouvelles = dict(corrections)
    for numero, colonnes in lignes_modifiees.items():
        if COLONNE_CATEGORIE not in colonnes:
            continue
        marchand = marchands[int(numero)].marchand
        libelle = colonnes[COLONNE_CATEGORIE]
        cle = _CLES_PAR_LIBELLE.get(libelle) if libelle else AUTRE
        if cle is None:
            raise ValueError(f"Catégorie inconnue « {libelle} ».")
        if cle == AUTRE:
            nouvelles.pop(marchand, None)
        else:
            nouvelles[marchand] = cle
    return nouvelles


def corrections_en_csv(corrections: dict[str, str]) -> bytes:
    """Fichier à télécharger : marchand,categorie (clés de taux.csv), trié par marchand."""
    sortie = io.StringIO()
    ecrivain = csv.writer(sortie, lineterminator="\n")
    ecrivain.writerow(["marchand", "categorie"])
    for marchand in sorted(corrections):
        ecrivain.writerow([marchand, corrections[marchand]])
    return sortie.getvalue().encode("utf-8")


def lire_corrections_csv(contenu: bytes) -> dict[str, str]:
    """Relit un fichier produit par corrections_en_csv."""
    try:
        texte = contenu.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("Le fichier de corrections n'est pas en UTF-8.") from None
    lecteur = csv.DictReader(texte.splitlines())
    if lecteur.fieldnames is None or not {"marchand", "categorie"} <= set(lecteur.fieldnames):
        raise ValueError("Le fichier de corrections doit avoir les colonnes « marchand » et « categorie ».")
    corrections = {}
    for numero, ligne in enumerate(lecteur, start=2):
        marchand = (ligne["marchand"] or "").strip()
        categorie = (ligne["categorie"] or "").strip()
        if not marchand:
            raise ValueError(f"Corrections, ligne {numero} : marchand vide.")
        if categorie not in CATEGORIES:
            raise ValueError(f"Corrections, ligne {numero} : catégorie inconnue « {categorie} ».")
        if categorie != AUTRE:
            corrections[marchand] = categorie
    return corrections


# --- Mentions ---------------------------------------------------------------------

def lignes_sources(cartes: list[Carte]) -> list[dict]:
    return [
        {
            "Carte": c.nom,
            "Valeur retenue": valeur_du_point(c),
            "Frais annuels": formater_montant(c.frais_annuels),
            "Vérifiée le": c.verifie_le.isoformat() if c.verifie_le else "",
            "Source": c.source,
        }
        for c in cartes
    ]
