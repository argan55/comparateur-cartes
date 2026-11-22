"""L'interface tourne de bout en bout sur le relevé fictif (étape 4).

Les calculs sont testés ailleurs ; ici on vérifie que app.py affiche les
sections et réagit aux réglages sans planter.
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from src.cartes import charger_cartes
from tests.fictif import releve_fictif_annuel

APP = str(Path(__file__).parent.parent / "app.py")


@pytest.fixture
def app():
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.file_uploader(key="releve").upload("releve.csv", releve_fictif_annuel().encode(),
                                          "text/csv").run()
    assert not at.exception
    return at


def synthese(at) -> str:
    return next(m.value for m in at.markdown if "La carte la plus payante" in m.value)


def classement(at) -> list[str]:
    return list(at.dataframe[0].value["Valeur nette"])


def test_sans_releve_l_appli_attend_l_import():
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    assert not at.dataframe


def test_releve_affiche_periode_synthese_et_sections(app):
    assert any("novembre 2025 à octobre 2026" in m.value for m in app.markdown)
    assert synthese(app).count(":orange[") == 1
    assert [s.value for s in app.subheader] == [
        "En bref", "Classement", "Dépenses par catégorie",
        "Corriger les marchands non reconnus", "Mentions"]
    assert len(app.expander) == 9  # un détail par carte


def test_carte_actuelle_donne_l_ecart(app):
    derniere = app.dataframe[0].value["Carte"].iloc[-1]
    id_derniere = next(c.id for c in charger_cartes() if c.nom == derniere)
    app.selectbox(key="carte_actuelle").set_value(id_derniere).run()
    assert not app.exception
    assert "de plus par an" in synthese(app)
    assert synthese(app).endswith(f"ta carte actuelle, {derniere}.")


def test_interrupteur_livraison_change_le_classement(app):
    avant = classement(app)
    app.toggle(key="livraison").set_value(False).run()
    assert not app.exception
    assert classement(app) != avant


def test_correction_recalcule_le_classement(app):
    avant = classement(app)
    app.session_state["corrections"] = {"QUINCAILLERIE BIDON": "epicerie"}
    app.run()
    assert not app.exception
    assert classement(app) != avant
    assert app.data_editor[0].value["Catégorie"].iloc[0] == "Épicerie"
