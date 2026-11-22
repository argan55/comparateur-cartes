# Comparateur de cartes de crédit

Réponds en français. Tu écris les tests et le code, puis tu m'expliques ce que tu as fait ; je lis et je valide.

## Objectif
À partir de 12 mois de dépenses réelles (export CSV Desjardins), classer 5 à 10 cartes de crédit canadiennes selon leur valeur nette annuelle : remises en argent + points convertis en $, moins les frais annuels.

## Choix de la v1
- Données : export CSV Desjardins uniquement. Vérifier le format sur un vrai export avant d'écrire le lecteur.
- Catégorisation : règles par mots-clés de marchand ; ce qui n'est pas reconnu va dans « Autre » et peut être corrigé à la main dans l'appli. Le LLM (API Claude) pour les marchands inconnus est prévu en v1.1.
- Cartes : remises en argent et cartes à points ; chaque programme de points a une valeur fixe par point, affichée dans l'appli. Frais annuels et plafonds de remise pris en compte.
- Table des conditions des cartes remplie à la main, avec la source et la date de vérification de chaque carte.
- Hors v1 : autres banques, LLM, bonus de bienvenue, assurances, conditions de revenu, appli en ligne.

## Vie privée (dépôt public)
- Le dépôt GitHub sera public. Mon relevé réel ne doit jamais être commité ni envoyé nulle part : dossier `data/prive/` dans `.gitignore`, rien d'écrit sur disque depuis l'appli.
- Les exemples et les tests utilisent uniquement un relevé fictif.

## Conventions (reprises de l'Optimiseur de dettes)
- Toute la logique dans `src/`, testée avec pytest ; `app.py` ne fait qu'afficher.
- Montants en `Decimal`, arrondis au cent ; affichage à la québécoise (« 1 234,50 $ »).
- Thème Streamlit monochrome avec accent ambre (pas de vert).
- Le Python d'Anaconda refuse les certificats SSL sur ce PC : utiliser `truststore` si une requête réseau est nécessaire.
- Mets à jour la section « État » à la fin de chaque étape (fait, tests, prochaine étape).

## Étapes
1. Mise en place + lecture du CSV Desjardins
2. Catégorisation par règles + catégorie « Autre »
3. Table de 5 à 10 cartes + calcul de la valeur nette annuelle par carte
4. Interface Streamlit : import, répartition des dépenses, classement, correction des catégories
5. README, capture, publication GitHub (public)

## État
_À mettre à jour à la fin de chaque étape._
- 2026-11-22 : cadrage de la v1 fait, aucun code. Avant l'étape 1 : récupérer un export CSV Desjardins de 12 mois et choisir les cartes à comparer.
- 2026-11-22 : étape 1 faite. `src/desjardins.py` lit les exports carte (13 col.) et compte (16 col.), 23 tests, relevés fictifs dans `tests/donnees/`. Pas encore de dépôt git.
- 2026-11-22 : décisions — fenêtre = 12 derniers mois complets ; relevé de carte seulement (le compte est laissé de côté : double comptage avec les paiements de carte).
- 2026-11-22 : étape 2 faite, 75 tests. Lecteur : champ `marchand` (25 premiers caractères de la description en largeur fixe). `src/categories.py` : catégories = clés de `taux.csv`, sous-catégories de réseau avec parent (hypothèses : livraison → restaurants, abonnements → paiements récurrents), règles par mots-clés génériques (chaînes seulement : pas de marchands personnels dans le dépôt public). `src/depenses.py` : sélection achats + remboursements de carte, fenêtre, corrections `{marchand: catégorie}` en mémoire, répartition, marchands non reconnus.
- 2026-11-22 : règles enrichies après lecture des noms des marchands non reconnus (chaînes et mots génériques seulement ; commerces de quartier et enseignes trahissant un voyage laissés aux corrections manuelles). Correction de « MCDONALDS » ; « FRAIS DE CREDIT » a sa nature `frais`, exclue des dépenses. 99 tests.
- 2026-11-22 : étape 3 faite, 139 tests. `src/cartes.py` lit et valide `cartes.csv` + `taux.csv` (valeur $ = dépense × taux × valeur_point_cents / 100 ; revenu_min et frais_change_pct lus mais hors calcul). `src/calcul.py` : taux de la catégorie → parent → « autres » ; plafonds par groupe, sur l'année ou par mois civil, surplus au taux « autres », prorata dans un groupe partagé ; catégories au choix = meilleure combinaison ; total = somme des détails arrondis. Le classement peut dépendre beaucoup de l'hypothèse livraison → restaurants. Prochaine étape : étape 4 (interface Streamlit).
- 2026-11-22 : étape 4 faite, 181 tests (dont 5 AppTest sur un relevé fictif de 13 mois, `tests/fictif.py`). `src/affichage.py` : montants « 1 234,50 $ », phrase de synthèse (montant de la 1re carte seul en ambre, écart avec la carte actuelle), lignes du classement, du détail, des dépenses et des sources ; corrections : 20 marchands non reconnus par les règles (liste stable même une fois corrigés), application des modifications du tableau, CSV à télécharger et à recharger. `calcul.classer(..., livraison_est_restaurant)` pour l'interrupteur. `app.py` n'affiche que ; thème `.streamlit/config.toml` gris, ambre réservé à `:orange[]`. Vérifié dans Chrome avec le relevé fictif : correction dans le tableau (recalcul immédiat, bouton de téléchargement activé), interrupteur, carte actuelle, détails. Corrigé à cette occasion : graphique passé en `st.altair_chart` (noms entiers, axe au bon endroit), colonne « Valeur d'un point » retirée du classement (déjà dans le détail et les sources), montants alignés à droite. Prochaine étape : essai avec le vrai relevé, puis étape 5 (README, capture, publication).
- 2026-11-22 : étape 5 faite. README (fonctionnement, calculs, vie privée, cartes comparées, ajout d'une carte), 2 captures sur relevé fictif dans `docs/`, `altair` ajouté et Streamlit >= 1.67 dans `requirements.txt`. Vérification avant publication : aucun nom de marchand du vrai relevé dans les fichiers publiés, sauf chaînes et libellés génériques. Section « État » anonymisée ; les constats tirés du vrai relevé sont dans `data/prive/notes_releve_reel.md` (non publié). Dépôt public : https://github.com/argan55/comparateur-cartes. Prochaine étape : v1.1 (LLM pour les marchands inconnus).
