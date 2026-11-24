from google.adk.agents.context import Context
from google.adk.events.event import Event

from .config import MONEDAS_PERMITIDAS, UMBRAL_APROBACION_AUTO
from .schemas import ExpenseExtraction, ValidationResult


def validar_reglas(ctx: Context, node_input: ExpenseExtraction) -> Event:
    """Valida reglas de negocio en Python puro usando el límite del usuario autenticado."""
    # Prioridad: 1) límite inyectado del usuario autenticado (`user:limite_aprobacion`),
    #            2) límite global de la app (`app:umbral_aprobacion_auto`),
    #            3) valor por defecto en config.py (1000.0).
    umbral_app = float(ctx.state.get("app:umbral_aprobacion_auto", UMBRAL_APROBACION_AUTO))
    umbral = float(ctx.state.get("user:limite_aprobacion", umbral_app))
    user_rol = str(ctx.state.get("user:rol", "empleado"))
    moneda = node_input.moneda.upper()

    if node_input.monto <= 0:
        resultado = ValidationResult(
            expense=node_input,
            aprobacion_automatica=False,
            motivo=f"Monto inválido ({node_input.monto}). Debe ser mayor a 0.",
        )
        route = "rechazado"
    elif moneda not in MONEDAS_PERMITIDAS:
        resultado = ValidationResult(
            expense=node_input,
            aprobacion_automatica=False,
            motivo=f"Moneda '{moneda}' no permitida. Permitidas: {sorted(MONEDAS_PERMITIDAS)}.",
        )
        route = "requiere_humano"
    elif node_input.monto <= umbral:
        resultado = ValidationResult(
            expense=node_input,
            aprobacion_automatica=True,
            motivo=(
                f"Monto ({node_input.monto} {moneda}) dentro del límite automático "
                f"para rol '{user_rol}' (<= {umbral})."
            ),
        )
        route = "auto_aprobado"
    else:
        resultado = ValidationResult(
            expense=node_input,
            aprobacion_automatica=False,
            motivo=(
                f"Monto ({node_input.monto} {moneda}) supera el umbral de {umbral} "
                f"para rol '{user_rol}'; requiere aprobación humana."
            ),
        )
        route = "requiere_humano"

    return Event(
        output=resultado.model_dump(),
        route=route,
        state={
            "app:umbral_aprobacion_auto": umbral_app,
            "gasto_actual": resultado.model_dump(),
            "workflow_step": route,
            "temp:motivo_validacion": resultado.motivo,
        },
    )
