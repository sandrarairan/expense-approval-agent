import sqlite3
from typing import Any, Dict, List

from ..config import APP_DB_PATH, logger
from ..schemas import ExpenseExtraction


def save_expense_record(
    user_id: str,
    user_rol: str,
    expense: ExpenseExtraction,
    tipo_aprobacion: str,
    estado: str,
) -> Dict[str, Any]:
    """Persiste el gasto en la App DB local con auditoría del usuario autenticado."""
    try:
        with sqlite3.connect(APP_DB_PATH) as conn:
            cursor = conn.execute(
                """
                INSERT INTO expenses (
                    user_id, user_rol, concepto, monto, moneda,
                    categoria, proveedor, tipo_aprobacion, estado
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    user_rol,
                    expense.concepto,
                    expense.monto,
                    expense.moneda.upper(),
                    expense.categoria,
                    expense.proveedor,
                    tipo_aprobacion,
                    estado,
                ),
            )
            conn.commit()
            expense_id = cursor.lastrowid

        logger.info(
            "Gasto #%s guardado (%s) por %s [%s]: %s - %s %s",
            expense_id,
            estado,
            user_id,
            user_rol,
            expense.concepto,
            expense.monto,
            expense.moneda,
        )
        return {"status": "success", "expense_id": expense_id}
    except Exception as e:
        logger.error("Error guardando gasto en App DB: %s", e)
        return {"status": "error", "message": str(e)}


def list_registered_expenses(limit: int = 10) -> List[Dict[str, Any]]:
    """Consulta los últimos gastos guardados en la App DB local."""
    with sqlite3.connect(APP_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM expenses ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
