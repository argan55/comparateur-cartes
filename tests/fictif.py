"""Relevé de carte Desjardins fictif sur 13 mois (novembre 2025 → novembre 2026).

La fenêtre retenue est donc novembre 2025 → octobre 2026 : la transaction de
novembre 2026 ne sert qu'à marquer le mois en cours de l'export.
Tous les marchands sont inventés (sauf les mots-clés génériques des règles).
"""

# (marchand, ville, montant mensuel) : catégories attendues en commentaire
ACHATS_MENSUELS = [
    ("METRO FICTIF", "MONTREAL", "200.00"),          # epicerie
    ("UBER EATS FICTIF", "MONTREAL", "60.00"),       # livraison_repas
    ("RESTO LA FOURCHETTE", "LAVAL", "40.00"),        # restaurants
    ("QUINCAILLERIE BIDON", "QUEBEC", "100.00"),      # autres
    ("LIBRAIRIE IMAGINAIRE", "QUEBEC", "20.00"),      # autres
]


def _ligne(jour: str, numero: int, description: str, achat: str = "", credit: str = "") -> str:
    achat = achat or '""'
    credit = credit or '""'
    return (f'Remises Fictive **** 0000,"","",{jour},{numero:05d},{description},'
            f'"","","","","",{achat},{credit}')


def _description(marchand: str, ville: str) -> str:
    return f"{marchand:<25}{ville:<13}QC "


def releve_fictif_annuel() -> str:
    lignes = []
    numero = 1
    mois = [(2025, 11), (2025, 12)] + [(2026, m) for m in range(1, 11)]
    for annee, m in mois:
        for marchand, ville, montant in ACHATS_MENSUELS:
            lignes.append(_ligne(f"{annee}/{m:02d}/10", numero, _description(marchand, ville),
                                 achat=montant))
            numero += 1
        lignes.append(_ligne(f"{annee}/{m:02d}/25", numero, f"{'PAIEMENT CAISSE':<41}",
                             credit="420.00"))
        numero += 1
    # Mois en cours de l'export : hors fenêtre
    lignes.append(_ligne("2026/11/05", numero, _description("METRO FICTIF", "MONTREAL"),
                         achat="999.00"))
    return "\n".join(lignes) + "\n"
