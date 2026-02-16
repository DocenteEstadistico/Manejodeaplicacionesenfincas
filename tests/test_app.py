from pathlib import Path

from app import create_app, init_db


def test_no_permite_aplicar_mas_area(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    init_db(db_path)
    app = create_app(db_path)
    app.config["TESTING"] = True

    with app.test_client() as client:
        response = client.post(
            "/",
            data={
                "fecha": "2026-01-10",
                "finca_id": "1",
                "lote_id": "1",
                "mezcla_id": "1",
                "manzanas": "11",
            },
            follow_redirects=True,
        )

    assert "Solo faltan 10.00 en este lote" in response.get_data(as_text=True)


def test_resumen_muestra_totales(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    init_db(db_path)
    app = create_app(db_path)
    app.config["TESTING"] = True

    with app.test_client() as client:
        client.post(
            "/",
            data={
                "fecha": "2026-01-10",
                "finca_id": "1",
                "lote_id": "1",
                "mezcla_id": "1",
                "manzanas": "6",
            },
            follow_redirects=True,
        )
        resumen = client.get("/resumen")

    html = resumen.get_data(as_text=True)
    assert "Producto A" in html
    assert "9.00" in html
