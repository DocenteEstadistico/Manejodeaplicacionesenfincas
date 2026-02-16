from __future__ import annotations

import io
import sqlite3
from collections.abc import Iterator
from contextlib import closing
from datetime import date, datetime
from pathlib import Path

from flask import Flask, Response, flash, g, redirect, render_template, request, send_file, url_for
from openpyxl import Workbook

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = BASE_DIR / "fincas.db"


def create_app(db_path: Path | None = None) -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "dev-secret-key"
    app.config["DB_PATH"] = db_path or DEFAULT_DB_PATH

    @app.before_request
    def _ensure_db() -> None:
        init_db(app.config["DB_PATH"])

    @app.teardown_appcontext
    def _close_db(_: object) -> None:
        db = g.pop("db", None)
        if db is not None:
            db.close()

    @app.route("/", methods=["GET", "POST"])
    def index() -> str | Response:
        db = get_db(app.config["DB_PATH"])
        fincas = db.execute("SELECT id, nombre FROM fincas ORDER BY id").fetchall()
        mezclas = db.execute("SELECT id, nombre FROM mezclas ORDER BY id").fetchall()

        selected_finca_id = int(request.form.get("finca_id") or request.args.get("finca_id") or fincas[0]["id"])
        lotes = db.execute(
            "SELECT id, nombre, area_total FROM lotes WHERE finca_id = ? ORDER BY id",
            (selected_finca_id,),
        ).fetchall()
        selected_lote_id = int(request.form.get("lote_id") or request.args.get("lote_id") or lotes[0]["id"])

        if request.method == "POST":
            fecha_raw = request.form.get("fecha", "")
            mezcla_id = int(request.form["mezcla_id"])
            manzanas = float(request.form["manzanas"]) if request.form.get("manzanas") else 0

            try:
                fecha = datetime.strptime(fecha_raw, "%Y-%m-%d").date()
            except ValueError:
                flash("La fecha no tiene un formato válido.", "error")
                return redirect(url_for("index", finca_id=selected_finca_id, lote_id=selected_lote_id))

            estado = lote_estado(db, selected_lote_id)
            restante = estado["restante"]

            if manzanas <= 0:
                flash("Las manzanas aplicadas deben ser mayores que 0.", "error")
            elif manzanas > restante:
                flash(
                    f"No se pueden aplicar {manzanas} manzanas. Solo faltan {restante:.2f} en este lote.",
                    "error",
                )
            else:
                db.execute(
                    """
                    INSERT INTO aplicaciones (fecha, finca_id, lote_id, mezcla_id, manzanas_aplicadas)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (fecha.isoformat(), selected_finca_id, selected_lote_id, mezcla_id, manzanas),
                )
                db.commit()
                flash("Aplicación guardada correctamente.", "success")

            return redirect(url_for("index", finca_id=selected_finca_id, lote_id=selected_lote_id))

        estado_lote = lote_estado(db, selected_lote_id)
        historial = db.execute(
            """
            SELECT a.fecha, f.nombre AS finca, l.nombre AS lote, m.nombre AS mezcla, a.manzanas_aplicadas
            FROM aplicaciones a
            JOIN fincas f ON f.id = a.finca_id
            JOIN lotes l ON l.id = a.lote_id
            JOIN mezclas m ON m.id = a.mezcla_id
            ORDER BY a.fecha DESC, a.id DESC
            LIMIT 15
            """
        ).fetchall()

        return render_template(
            "index.html",
            fincas=fincas,
            lotes=lotes,
            mezclas=mezclas,
            selected_finca_id=selected_finca_id,
            selected_lote_id=selected_lote_id,
            estado_lote=estado_lote,
            historial=historial,
            today=date.today().isoformat(),
        )


    @app.get("/api/lote_estado/<int:lote_id>")
    def api_lote_estado(lote_id: int) -> dict[str, float]:
        db = get_db(app.config["DB_PATH"])
        estado = lote_estado(db, lote_id)
        return {
            "area_total": float(estado["area_total"]),
            "aplicadas": float(estado["aplicadas"]),
            "restante": float(estado["restante"]),
        }

    @app.get("/resumen")
    def resumen() -> str:
        db = get_db(app.config["DB_PATH"])
        detalle = obtener_detalle_producto(db)
        totales = obtener_totales_producto(db)
        return render_template("resumen.html", detalle=detalle, totales=totales)

    @app.get("/export/excel")
    def export_excel() -> Response:
        db = get_db(app.config["DB_PATH"])
        detalle = obtener_detalle_producto(db)
        totales = obtener_totales_producto(db)

        wb = Workbook()
        ws1 = wb.active
        ws1.title = "Detalle por finca-lote"
        ws1.append(["Finca", "Lote", "Producto", "Litros utilizados"])
        for row in detalle:
            ws1.append([row["finca"], row["lote"], row["producto"], float(row["litros_utilizados"])])

        ws2 = wb.create_sheet("Totales por producto")
        ws2.append(["Producto", "Litros totales"])
        for row in totales:
            ws2.append([row["producto"], float(row["litros_totales"])])

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return send_file(
            output,
            as_attachment=True,
            download_name="reporte_aplicaciones.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    return app


def get_db(db_path: Path) -> sqlite3.Connection:
    if "db" not in g:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        g.db = conn
    return g.db


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(db_path)) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS fincas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                area_total REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS lotes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                finca_id INTEGER NOT NULL,
                nombre TEXT NOT NULL,
                area_total REAL NOT NULL,
                FOREIGN KEY (finca_id) REFERENCES fincas(id)
            );

            CREATE TABLE IF NOT EXISTS mezclas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS mezcla_productos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mezcla_id INTEGER NOT NULL,
                producto TEXT NOT NULL,
                dosis_litros_manzana REAL NOT NULL,
                FOREIGN KEY (mezcla_id) REFERENCES mezclas(id)
            );

            CREATE TABLE IF NOT EXISTS aplicaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL,
                finca_id INTEGER NOT NULL,
                lote_id INTEGER NOT NULL,
                mezcla_id INTEGER NOT NULL,
                manzanas_aplicadas REAL NOT NULL,
                FOREIGN KEY (finca_id) REFERENCES fincas(id),
                FOREIGN KEY (lote_id) REFERENCES lotes(id),
                FOREIGN KEY (mezcla_id) REFERENCES mezclas(id)
            );
            """
        )

        count_fincas = conn.execute("SELECT COUNT(*) FROM fincas").fetchone()[0]
        if count_fincas == 0:
            for finca_num in range(1, 11):
                nombre_finca = f"Finca {finca_num}"
                conn.execute(
                    "INSERT INTO fincas (nombre, area_total) VALUES (?, ?)",
                    (nombre_finca, 70),
                )
                finca_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                for lote_num in range(1, 8):
                    conn.execute(
                        "INSERT INTO lotes (finca_id, nombre, area_total) VALUES (?, ?, ?)",
                        (finca_id, f"Lote {lote_num}", 10),
                    )

        count_mezclas = conn.execute("SELECT COUNT(*) FROM mezclas").fetchone()[0]
        if count_mezclas == 0:
            conn.execute("INSERT INTO mezclas (nombre) VALUES (?)", ("Mezcla 1",))
            mezcla_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.executemany(
                "INSERT INTO mezcla_productos (mezcla_id, producto, dosis_litros_manzana) VALUES (?, ?, ?)",
                [
                    (mezcla_id, "Producto A", 1.5),
                    (mezcla_id, "Producto B", 2.0),
                    (mezcla_id, "Producto C", 0.5),
                ],
            )

        conn.commit()


def lote_estado(db: sqlite3.Connection, lote_id: int) -> sqlite3.Row:
    return db.execute(
        """
        SELECT l.area_total,
               COALESCE(SUM(a.manzanas_aplicadas), 0) AS aplicadas,
               l.area_total - COALESCE(SUM(a.manzanas_aplicadas), 0) AS restante
        FROM lotes l
        LEFT JOIN aplicaciones a ON a.lote_id = l.id
        WHERE l.id = ?
        GROUP BY l.id
        """,
        (lote_id,),
    ).fetchone()


def obtener_detalle_producto(db: sqlite3.Connection) -> Iterator[sqlite3.Row]:
    return db.execute(
        """
        SELECT f.nombre AS finca,
               l.nombre AS lote,
               mp.producto,
               ROUND(SUM(a.manzanas_aplicadas * mp.dosis_litros_manzana), 2) AS litros_utilizados
        FROM aplicaciones a
        JOIN fincas f ON f.id = a.finca_id
        JOIN lotes l ON l.id = a.lote_id
        JOIN mezcla_productos mp ON mp.mezcla_id = a.mezcla_id
        GROUP BY f.id, l.id, mp.producto
        ORDER BY f.id, l.id, mp.producto
        """
    ).fetchall()


def obtener_totales_producto(db: sqlite3.Connection) -> Iterator[sqlite3.Row]:
    return db.execute(
        """
        SELECT mp.producto,
               ROUND(SUM(a.manzanas_aplicadas * mp.dosis_litros_manzana), 2) AS litros_totales
        FROM aplicaciones a
        JOIN mezcla_productos mp ON mp.mezcla_id = a.mezcla_id
        GROUP BY mp.producto
        ORDER BY mp.producto
        """
    ).fetchall()


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
