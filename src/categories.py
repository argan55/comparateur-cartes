"""Catégories de dépenses et règles par mots-clés de marchand (étape 2).

Les clés des catégories sont celles de data/taux.csv. Une sous-catégorie de
réseau (ex. IGA → epicerie_reseau_sobeys) a un parent : une carte qui n'a pas
de taux pour la sous-catégorie applique celui du parent (étape 3).
"""

import re
import unicodedata
from dataclasses import dataclass

AUTRE = "autres"
LIVRAISON = "livraison_repas"


@dataclass(frozen=True)
class Categorie:
    libelle: str
    parent: str | None = None


CATEGORIES: dict[str, Categorie] = {
    "epicerie": Categorie("Épicerie"),
    "epicerie_reseau_sobeys": Categorie("Épicerie – réseau Sobeys (IGA)", "epicerie"),
    "restaurants": Categorie("Restaurants"),
    # Hypothèse : la livraison de repas est comptée comme restaurant par les cartes sans taux propre.
    "livraison_repas": Categorie("Livraison de repas", "restaurants"),
    "essence": Categorie("Essence"),
    "transport_commun": Categorie("Transport en commun et taxi"),
    "covoiturage": Categorie("Covoiturage (Uber, Lyft…)"),
    "pharmacie": Categorie("Pharmacie"),
    "pharmacie_reseau_loblaw": Categorie("Pharmacie – réseau Loblaw (Pharmaprix)", "pharmacie"),
    "paiements_recurrents": Categorie("Paiements récurrents (factures)"),
    # Hypothèse : un abonnement numérique est un paiement récurrent pour les cartes sans taux propre.
    "abonnements_numeriques": Categorie("Abonnements numériques", "paiements_recurrents"),
    "divertissement": Categorie("Divertissement"),
    "divertissement_cineplex": Categorie("Divertissement – Cineplex", "divertissement"),
    AUTRE: Categorie("Autre"),
}

# Règles par ordre de priorité : la première qui correspond l'emporte.
# Les mots-clés sont comparés mot entier, après normaliser().
REGLES: list[tuple[str, list[str]]] = [
    # Avant « UBER » (covoiturage) et « RESTO » (restaurants)
    ("livraison_repas", [
        "UBEREATS", "UBER EATS", "DOORDASH", "SKIPTHEDISHES", "SKIP THE DISHES", "FANTUAN",
    ]),
    # Avant les paiements récurrents
    ("abonnements_numeriques", [
        "NETFLIX", "SPOTIFY", "DISNEY PLUS", "DISNEYPLUS", "CRAVE", "APPLE COM BILL",
        "PRIME VIDEO", "AMAZON PRIME", "PRIME MEMBER", "AUDIBLE", "YOUTUBE PREMIUM",
        "GOOGLE YOUTUBE", "CRUNCHYROLL", "PARAMOUNT", "ILLICO", "TOU TV", "ICLOUD",
        "PLAYSTATION NETWORK", "XBOX", "OPENAI", "CHATGPT", "ANTHROPIC", "CLAUDE AI",
        "NORTON",
    ]),
    # Sous-catégories de réseau, avant leur catégorie générale
    ("epicerie_reseau_sobeys", [
        "IGA", "SOBEYS", "SAFEWAY", "FOODLAND", "FRESHCO", "THRIFTY FOODS",
        "MARCHE TRADITION", "BONICHOIX",
    ]),
    ("pharmacie_reseau_loblaw", ["PHARMAPRIX", "SHOPPERS DRUG MART", "SHOPPERS DRUG"]),
    ("divertissement_cineplex", ["CINEPLEX"]),
    # « COSTCO GAS » doit passer avant tout ; Costco seul reste dans « Autre »
    ("essence", [
        "COSTCO GAS", "COSTCO ESSENCE", "ESSO", "SHELL", "PETRO CANADA", "ULTRAMAR",
        "IRVING", "PIONEER", "HUSKY", "SONIC", "OLCO", "CROSSROADS", "CDN TIRE GAS",
        "CANADIAN TIRE GAS", "GAS BAR", "STATION SERVICE",
    ]),
    ("paiements_recurrents", [
        "HYDRO QUEBEC", "ENERGIR", "VIDEOTRON", "BELL", "BELL CANADA", "FIZZ", "ROGERS",
        "TELUS", "KOODO", "FIDO", "VIRGIN PLUS", "PUBLIC MOBILE", "COGECO", "EBOX",
        "ENERGIE CARDIO", "ECONOFITNESS", "NAUTILUS PLUS", "GOODLIFE",
    ]),
    ("covoiturage", ["UBER", "LYFT", "EVA COOP"]),
    ("transport_commun", [
        "STM", "OPUS", "EXO", "RTC", "STL", "RTL", "ARTM", "VIA RAIL", "BIXI", "TAXI",
        "COMMUNAUTO", "ORLEANS EXPRESS",
    ]),
    ("pharmacie", [
        "JEAN COUTU", "FAMILIPRIX", "PROXIM", "UNIPRIX", "BRUNET", "PHARMACIE",
        "LONDON DRUGS", "REXALL",
    ]),
    ("epicerie", [
        "METRO", "SUPER C", "MAXI", "PROVIGO", "LOBLAWS", "ADONIS", "AVRIL",
        "MARCHE", "FRUITERIE", "BOUCHERIE", "EPICERIE", "PA SUPERMARCHE",
        "INTERMARCHE", "MOURELATOS", "T&T", "RACHELLE BERY", "SUPERMARCHE",
        "ALIMENTATION",
    ]),
    ("restaurants", [
        "RESTAURANT", "RESTO", "TIM HORTONS", "TIM HORTON", "STARBUCKS", "SECOND CUP",
        "MCDONALD", "MCDONALDS", "A&W", "SUBWAY", "KFC", "BURGER", "PIZZA", "SUSHI",
        "BISTRO", "BRASSERIE", "CAFE", "BAR", "PUB", "ST HUBERT", "BENNY", "CORA",
        "POULET", "DOMINOS", "COFFEE", "LA BELLE PROVINCE", "3 BRASSEURS", "WENDY S",
        "WENDYS", "DAIRY QUEEN", "KRISPY KREME", "PIZZA PIZZA", "DELI", "BAGEL",
        "BAGELS", "TACOS", "DONER", "GRILL", "CREMERIE", "BAR LAITIER",
        "TST",  # Toast : terminal de paiement utilisé presque seulement par des restaurants
        "TGTG", "TOO GOOD TO GO",  # invendus de boulangeries et restaurants
    ]),
    ("divertissement", [
        "CINE STARZ", "STEAM", "STEAMGAMES", "INSTANT GAMING",
        "TICKETMASTER", "EVENBRITE", "CINEMA", "CINEMAS", "GUZZO", "THEATRE", "MUSEE",
        "BOWLING", "SPECTACLE",
    ]),
]


def normaliser(texte: str) -> str:
    """Majuscules, sans accents ; toute ponctuation (sauf &) devient une espace."""
    sans_accents = "".join(
        c for c in unicodedata.normalize("NFKD", texte) if not unicodedata.combining(c)
    )
    return " ".join(re.sub(r"[^A-Z0-9&]", " ", sans_accents.upper()).split())


def _motif(mots_cles: list[str]) -> re.Pattern:
    # Mot entier : ni lettre, ni chiffre, ni & juste avant ou juste après.
    choix = "|".join(re.escape(normaliser(m)) for m in mots_cles)
    return re.compile(rf"(?<![A-Z0-9&])(?:{choix})(?![A-Z0-9&])")


_REGLES_COMPILEES = [(categorie, _motif(mots)) for categorie, mots in REGLES]


def categoriser(marchand: str) -> str:
    """Renvoie la clé de catégorie du marchand, ou AUTRE si aucune règle ne correspond."""
    texte = normaliser(marchand)
    for categorie, motif in _REGLES_COMPILEES:
        if motif.search(texte):
            return categorie
    return AUTRE


def parents(categorie: str) -> list[str]:
    """La catégorie, puis son parent s'il existe (ordre de recherche des taux)."""
    parent = CATEGORIES[categorie].parent
    return [categorie] if parent is None else [categorie, parent]
