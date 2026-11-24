"""
Ejecutor local con autenticación externa (Opción A, sin IAP) + persistencia (03b + 03c):
- La autenticación ocurre ANTES del agente (`authenticate_token`), no dentro del prompt.
- La identidad verificada (`user:id`, `user:nombre`, `user:rol`, `user:limite_aprobacion`)
  se inyecta en `session.state` al crear la sesión.
- Mañana puedes reemplazar `authenticate_token` por JWT, Firebase Auth, Auth0 o IAP sin tocar el agente.

Ejecutar desde la raíz del repo:
    .venv/bin/python -m expense_approval_agent.run_with_persistence
"""
import asyncio

from google.adk.memory import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from google.genai import types

from .agent import root_agent
from .auth import authenticate_token
from .config import SESSION_DB_URL, UMBRAL_APROBACION_AUTO
from .tools import list_registered_expenses


async def main() -> None:
    # 1. Autenticación externa (antes de tocar el Runner o Gemini)
    current_user = authenticate_token("tok_ana_empleado")

    app_name = "expense_approval_app"
    user_id = current_user["user_id"]
    session_id = "session_gasto_001"

    # 2. Persistencia de sesiones en SQLite (03b) + Memoria local (03c)
    session_service = DatabaseSessionService(db_url=SESSION_DB_URL)
    memory_service = InMemoryMemoryService()

    existing = await session_service.get_session(
        app_name=app_name, user_id=user_id, session_id=session_id
    )
    if existing is None:
        await session_service.create_session(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            state={
                "app:umbral_aprobacion_auto": UMBRAL_APROBACION_AUTO,
                "user:id": current_user["user_id"],
                "user:nombre": current_user["nombre"],
                "user:rol": current_user["rol"],
                "user:limite_aprobacion": current_user["limite_aprobacion"],
                "user:total_gastos_aprobados": 0.0,
            },
        )

    runner = Runner(
        app_name=app_name,
        agent=root_agent,
        session_service=session_service,
        memory_service=memory_service,
    )

    mensaje = types.Content(
        role="user",
        parts=[types.Part.from_text(text="Factura de licencias de software por 250 USD de JetBrains")],
    )

    print(f"Usuario autenticado: {current_user['nombre']} ({current_user['rol']}, límite <= {current_user['limite_aprobacion']})")
    async for event in runner.run_async(
        user_id=user_id, session_id=session_id, new_message=mensaje
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    print(part.text)

    updated_session = await session_service.get_session(
        app_name=app_name, user_id=user_id, session_id=session_id
    )
    if updated_session:
        await memory_service.add_session_to_memory(updated_session)
        print("\nEstado persistido en SQLite:", updated_session.state)

    print("\nÚltimos gastos en App DB (expenses_app.db):", list_registered_expenses(limit=5))


if __name__ == "__main__":
    asyncio.run(main())
