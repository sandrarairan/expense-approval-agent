import logging
from pathlib import Path
import sqlite3
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("expense_approval_agent")

# Reglas de negocio globales (fallback si el usuario no tiene límite personalizado)
UMBRAL_APROBACION_AUTO = 1000.0
MONEDAS_PERMITIDAS = {"USD", "EUR", "MXN", "COP"}

# Base de datos de la aplicación (patrón 03d: App DB separada de Session State, en SQLite local)
BASE_DIR = Path(__file__).resolve().parent
APP_DB_PATH = BASE_DIR / "expenses_app.db"
SESSION_DB_URL = f"sqlite+aiosqlite:///{BASE_DIR / 'expense_sessions.db'}"


def init_app_db() -> None:
    """Inicializa la tabla de gastos registrados en la App DB local con trazabilidad de usuario."""
    with sqlite3.connect(APP_DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                user_rol TEXT NOT NULL,
                concepto TEXT NOT NULL,
                monto REAL NOT NULL,
                moneda TEXT NOT NULL,
                categoria TEXT NOT NULL,
                proveedor TEXT,
                tipo_aprobacion TEXT NOT NULL,
                estado TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        # Migración ligera si la tabla ya existía sin user_id/user_rol
        cols = {row[1] for row in conn.execute("PRAGMA table_info(expenses)").fetchall()}
        if "user_id" not in cols:
            conn.execute("ALTER TABLE expenses ADD COLUMN user_id TEXT NOT NULL DEFAULT 'unknown'")
        if "user_rol" not in cols:
            conn.execute("ALTER TABLE expenses ADD COLUMN user_rol TEXT NOT NULL DEFAULT 'empleado'")
        conn.commit()


init_app_db()
