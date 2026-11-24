from google.adk.agents.context import Context
from google.adk.events.event import Event
from google.adk.workflow import Workflow
from google.genai import types

from .rules import validar_reglas
from .schemas import ValidationResult
from .subagents import extractor_agent
from .tools import save_expense_record


def _extract_user_text(node_input) -> str:
    """Extrae texto plano del mensaje del usuario (types.Content o str)."""
    if isinstance(node_input, str):
        return node_input
    if hasattr(node_input, "parts") and node_input.parts:
        return " ".join(p.text for p in node_input.parts if getattr(p, "text", None))
    return str(node_input)


# 0. Nodo de entrada (02c + 03a): decide si el mensaje es un gasto nuevo o una respuesta HITL
def recibir_entrada(ctx: Context, node_input):
    if ctx.state.get("workflow_step") == "requiere_humano" and ctx.state.get("gasto_actual"):
        respuesta_usuario = _extract_user_text(node_input)
        return Event(output=respuesta_usuario, route="responder_aprobacion")
    return Event(output=node_input, route="nuevo_gasto")


# 1a. Pausa HITL: muestra los datos del gasto pendiente y espera respuesta humana en el siguiente turno
def solicitar_aprobacion(ctx: Context, node_input: ValidationResult):
    exp = node_input.expense
    solicitante = ctx.state.get("user:nombre") or ctx.session.user_id
    mensaje = (
        f"⚠️ Aprobación humana requerida:\n"
        f"- Solicitante: {solicitante}\n"
        f"- Concepto: {exp.concepto}\n"
        f"- Monto: {exp.monto} {exp.moneda}\n"
        f"- Categoría: {exp.categoria}\n"
        f"- Motivo: {node_input.motivo}\n\n"
        f"¿Apruebas este gasto? Responde 'aprobar' o 'rechazar'."
    )
    yield Event(
        content=types.Content(role="model", parts=[types.Part.from_text(text=mensaje)]),
        state={"workflow_step": "requiere_humano"},
    )
    yield Event(output={"estado": "pendiente_aprobacion", "gasto": exp.model_dump()})


# 1b. Procesa la respuesta humana leyendo el gasto guardado en session.state (sin re-llamar al LLM)
def procesar_aprobacion_humana(ctx: Context, node_input: str):
    respuesta = str(node_input).strip().lower()
    aprobado = any(
        palabra in respuesta
        for palabra in ("aprobar", "aprobado", "aprobada", "si", "sí", "yes", "ok")
    )
    gasto_actual = ctx.state.get("gasto_actual", {})
    if aprobado:
        return Event(output=gasto_actual, route="aprobado", state={"workflow_step": "aprobado_humano"})
    return Event(output=gasto_actual, route="rechazado", state={"workflow_step": "rechazado_humano"})


# 2. Nodos finales: Dual-Write (03d) -> guardan en App DB (SQLite) con identidad autenticada + user: state
def registrar(ctx: Context, node_input: ValidationResult):
    exp = node_input.expense
    modo = "automática" if node_input.aprobacion_automatica else "humana"
    user_id = str(ctx.state.get("user:id") or ctx.session.user_id or "anonymous")
    user_rol = str(ctx.state.get("user:rol", "empleado"))

    db_res = save_expense_record(
        user_id=user_id,
        user_rol=user_rol,
        expense=exp,
        tipo_aprobacion=modo,
        estado="registrado",
    )
    expense_id = db_res.get("expense_id", "-")

    total_previo = float(ctx.state.get("user:total_gastos_aprobados", 0.0))
    nuevo_total = total_previo + exp.monto

    texto = (
        f"✅ Gasto #{expense_id} registrado (aprobación {modo}):\n"
        f"- Usuario: {user_id} ({user_rol})\n"
        f"- Concepto: {exp.concepto}\n"
        f"- Monto: {exp.monto} {exp.moneda}\n"
        f"- Categoría: {exp.categoria}\n"
        f"- Detalle: {node_input.motivo}\n"
        f"- Acumulado del usuario: {nuevo_total}"
    )
    yield Event(
        content=types.Content(role="model", parts=[types.Part.from_text(text=texto)]),
        state={
            "user:total_gastos_aprobados": nuevo_total,
            "user:ultimo_gasto_id": expense_id,
            "workflow_step": "registrado",
        },
    )
    yield Event(output={"estado": "registrado", "expense_id": expense_id, "gasto": exp.model_dump()})


def rechazar(ctx: Context, node_input: ValidationResult):
    exp = node_input.expense
    user_id = str(ctx.state.get("user:id") or ctx.session.user_id or "anonymous")
    user_rol = str(ctx.state.get("user:rol", "empleado"))

    db_res = save_expense_record(
        user_id=user_id,
        user_rol=user_rol,
        expense=exp,
        tipo_aprobacion="rechazado",
        estado="rechazado",
    )
    expense_id = db_res.get("expense_id", "-")

    texto = (
        f"❌ Gasto #{expense_id} rechazado:\n"
        f"- Usuario: {user_id} ({user_rol})\n"
        f"- Concepto: {exp.concepto}\n"
        f"- Monto: {exp.monto} {exp.moneda}\n"
        f"- Motivo: {node_input.motivo}"
    )
    yield Event(
        content=types.Content(role="model", parts=[types.Part.from_text(text=texto)]),
        state={"workflow_step": "rechazado"},
    )
    yield Event(output={"estado": "rechazado", "expense_id": expense_id, "gasto": exp.model_dump()})


# 3. Grafo completo (root_agent que descubre `adk web` / `adk eval`)
root_agent = Workflow(
    name="expense_approval_workflow",
    description="Flujo de aprobación de gastos con extracción multimodal, validación determinista, estado y aprobación humana.",
    edges=[
        ("START", recibir_entrada),
        (
            recibir_entrada,
            {
                "nuevo_gasto": extractor_agent,
                "responder_aprobacion": procesar_aprobacion_humana,
            },
        ),
        (extractor_agent, validar_reglas),
        (
            validar_reglas,
            {
                "auto_aprobado": registrar,
                "requiere_humano": solicitar_aprobacion,
                "rechazado": rechazar,
            },
        ),
        (
            procesar_aprobacion_humana,
            {
                "aprobado": registrar,
                "rechazado": rechazar,
            },
        ),
    ],
)
