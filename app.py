"""Comparateur de cartes de crédit : interface Streamlit (étape 4).

Ce fichier ne fait qu'afficher ; les calculs et la mise en forme sont dans src/.
Le relevé est lu en mémoire : rien n'est écrit sur disque.
Lancer avec : streamlit run app.py
"""

import altair as alt
import streamlit as st

from src import affichage as af
from src.calcul import classer
from src.cartes import charger_cartes
from src.depenses import fenetre_12_mois_complets, preparer_depenses
from src.desjardins import lire_releve

AUCUNE = ""


@st.cache_data
def cartes():
    return charger_cartes()


def a_droite(*colonnes):
    """Montants alignés à droite (ce sont des textes déjà formatés « 1 234,50 $ »)."""
    return {c: st.column_config.TextColumn(alignment="right") for c in colonnes}


def _modifier_corrections():
    """Le tableau des corrections a changé : on met à jour les corrections."""
    lignes_modifiees = st.session_state["editeur_corrections"]["edited_rows"]
    st.session_state["corrections"] = af.appliquer_modifications(
        st.session_state["corrections"], st.session_state["marchands_a_corriger"], lignes_modifiees)


def _importer_corrections():
    fichier = st.session_state["fichier_corrections"]
    st.session_state["erreur_corrections"] = None
    if fichier is None:
        return
    try:
        st.session_state["corrections"] |= af.lire_corrections_csv(fichier.getvalue())
    except ValueError as erreur:
        st.session_state["erreur_corrections"] = str(erreur)
        return
    # Les modifications en cours du tableau sont remplacées par le fichier.
    st.session_state.pop("editeur_corrections", None)


# --- État de la session (en mémoire seulement) ---
st.session_state.setdefault("corrections", {})
st.session_state.setdefault("livraison", True)
st.session_state.setdefault("carte_actuelle", AUCUNE)
st.session_state.setdefault("erreur_corrections", None)

st.set_page_config(page_title="Comparateur de cartes", page_icon=":material/credit_card:")
st.title("Comparateur de cartes de crédit")

# --- 1. Import et période ---
fichier = st.file_uploader("Relevé CSV de ta carte de crédit Desjardins", type="csv", key="releve")
st.caption("Exporté d'AccèsD. Le fichier est lu en mémoire, jamais enregistré ni envoyé.")
if fichier is None:
    st.stop()

try:
    transactions = lire_releve(fichier.getvalue())
except ValueError as erreur:
    st.error(str(erreur), title="Relevé illisible")
    st.stop()
if all(t.source == "compte" for t in transactions):
    st.error("C'est un relevé de compte : importe plutôt celui de ta carte de crédit.",
             title="Mauvais relevé")
    st.stop()

depenses = preparer_depenses(transactions, st.session_state["corrections"])
if not depenses:
    st.error("Aucun achat de carte dans les 12 derniers mois complets du relevé.",
             title="Rien à comparer")
    st.stop()
debut, fin = fenetre_12_mois_complets(transactions)
st.markdown(af.pour_markdown(
    f"Période analysée : **{af.periode(debut, fin)}** (12 derniers mois complets) · "
    f"{len(depenses)} achats · {af.formater_montant(af.total_depenses(depenses))}"))

liste_cartes = cartes()
resultats = classer(liste_cartes, depenses, st.session_state["livraison"])

# --- 2. Synthèse ---
st.subheader("En bref")
st.markdown(af.phrase_synthese(resultats, st.session_state["carte_actuelle"]))
noms = {c.id: c.nom for c in liste_cartes}
st.selectbox("Ta carte actuelle", [AUCUNE, *noms], key="carte_actuelle",
             format_func=lambda id: noms.get(id, "Aucune / je préfère ne pas comparer"))

# --- 3. Classement ---
st.subheader("Classement")
st.caption("Valeur nette annuelle = remises et points convertis en $, moins les frais annuels.")
barres = af.barres_classement(resultats)
st.altair_chart(
    alt.Chart(alt.Data(values=barres)).mark_bar(color="#71717a").encode(
        x=alt.X("Valeur nette ($):Q", title="Valeur nette annuelle ($)"),
        y=alt.Y("Carte:N", sort=None, title=None, axis=alt.Axis(labelLimit=320, labelOverlap=False)),
        tooltip=["Carte:N", alt.Tooltip("Valeur nette ($):Q", format=".2f")],
    ).properties(height=36 * len(barres)),
    alt="Valeur nette annuelle de chaque carte, de la meilleure à la pire")
st.dataframe(af.lignes_classement(resultats), hide_index=True, alt="Classement des cartes",
             column_config=a_droite("Récompenses", "Frais annuels", "Valeur nette"))
for r in resultats:
    with st.expander(f"Détail du calcul — {r.carte.nom}"):
        st.dataframe(af.lignes_detail(r), hide_index=True,
                     alt=f"Récompense par catégorie pour {r.carte.nom}",
                     column_config=a_droite("Dépenses", "Rendement", "Récompense"))
        for note in af.notes_detail(r):
            st.markdown(af.pour_markdown(note))

# --- 4. Dépenses par catégorie ---
st.subheader("Dépenses par catégorie")
st.dataframe(af.lignes_repartition(depenses), hide_index=True, alt="Dépenses par catégorie",
             column_config=a_droite("Montant", "Part"))

# --- 5. Correction des catégories ---
st.subheader("Corriger les marchands non reconnus")
st.caption("Les 20 marchands que les règles n'ont pas reconnus et qui coûtent le plus. "
           "Choisis leur catégorie : le classement est recalculé tout de suite.")
marchands = af.marchands_a_corriger(transactions, st.session_state["corrections"])
st.session_state["marchands_a_corriger"] = marchands
if marchands:
    st.data_editor(
        af.lignes_corrections(marchands), key="editeur_corrections", hide_index=True,
        disabled=["Marchand", "Achats", "Total"], on_change=_modifier_corrections,
        column_config=a_droite("Total") | {af.COLONNE_CATEGORIE: st.column_config.SelectboxColumn(
            options=list(af.LIBELLES.values()), required=True)},
        alt="Marchands non reconnus et leur catégorie",
    )
else:
    st.markdown("Tous les marchands ont été reconnus.")

with st.container(horizontal=True, vertical_alignment="bottom"):
    st.download_button("Télécharger mes corrections", af.corrections_en_csv(
        st.session_state["corrections"]), file_name="corrections_categories.csv",
        mime="text/csv", icon=":material/download:",
        disabled=not st.session_state["corrections"])
    st.file_uploader("Recharger des corrections", type="csv", key="fichier_corrections",
                     on_change=_importer_corrections)
if st.session_state["erreur_corrections"]:
    st.error(st.session_state["erreur_corrections"], title="Corrections illisibles")
st.caption("Le fichier contient les noms de tes marchands : range-le dans `data/prive/`, "
           "qui n'est jamais publié.")

# --- 6. Hypothèse livraison ---
st.toggle("Livraison de repas = restaurant", key="livraison",
          help="Activé : les cartes sans taux propre à la livraison (Uber Eats, DoorDash…) lui "
               "appliquent leur taux restaurants. Désactivé : leur taux de base.")

# --- 7. Mentions ---
st.subheader("Mentions")
st.markdown(
    "- Conditions saisies à la main ; vérifie-les auprès de l'émetteur avant de demander une carte.\n"
    "- Chaque point vaut une valeur fixe (colonne « Valeur retenue ») ; sa valeur réelle dépend "
    "de la façon de l'échanger.\n"
    "- Plafonds de remise pris en compte ; les plafonds mensuels sont appliqués par mois civil.\n"
    "- Non pris en compte : bonus de bienvenue, assurances, conditions de revenu, frais de change.\n"
    "- Seuls les achats et remboursements de la carte comptent (ni paiements, ni intérêts).\n"
    "- Rien n'est enregistré : fermer la page efface le relevé et les corrections non téléchargées."
)
st.dataframe(af.lignes_sources(liste_cartes), hide_index=True, alt="Sources des conditions des cartes",
             column_config=a_droite("Frais annuels") | {
                 "Source": st.column_config.LinkColumn(display_text="Site de l'émetteur")})
