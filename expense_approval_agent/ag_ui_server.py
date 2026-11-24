"""
Servidor AG-UI (FastAPI + ag-ui-adk) con autenticación multi-usuario (SQLite + JWT)
para conectar `expense_approval_agent` con CopilotKit v2 en React / Next.js.

Ejecutar desde la raíz del repo:
    .venv/bin/python -m expense_approval_agent.ag_ui_server
"""
import os
from typing import Any, Dict, Literal, Optional

from ag_ui.core import RunAgentInput
from ag_ui_adk import ADKAgent, add_adk_fastapi_endpoint
from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from google.adk.memory import InMemoryMemoryService
from google.adk.sessions import DatabaseSessionService
from pydantic import BaseModel

from .agent import root_agent
from .auth import (
    authenticate_token,
    create_access_token,
    extract_bearer_token,
    login_user,
    register_user,
)
from .config import SESSION_DB_URL, UMBRAL_APROBACION_AUTO


class RegisterRequest(BaseModel):
    email: str
    password: str
    nombre: str
    rol: Literal["empleado", "gerente", "director"] = "empleado"


class LoginRequest(BaseModel):
    email: str
    password: str


def require_authenticated_user(
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """Dependencia FastAPI que protege el endpoint AG-UI antes de llegar al agente."""
    try:
        token = extract_bearer_token(authorization)
        return authenticate_token(token)
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


async def extract_verified_user_state(
    request: Request,
    input_data: RunAgentInput,  # noqa: ARG001 - requerido por la firma de ag_ui_adk
) -> Dict[str, Any]:
    """
    Inyecta la identidad verificada en `session.state` sobrescribiendo cualquier
    valor enviado por el navegador (evita spoofing de rol o límite de aprobación).
    """
    user = require_authenticated_user(request.headers.get("authorization"))
    return {
        "user_id": user["user_id"],
        "app:umbral_aprobacion_auto": UMBRAL_APROBACION_AUTO,
        "user:id": user["user_id"],
        "user:nombre": user["nombre"],
        "user:rol": user["rol"],
        "user:limite_aprobacion": user["limite_aprobacion"],
    }


def _resolve_user_id(input_data: RunAgentInput) -> str:
    """Resuelve el `user_id` desde el estado inyectado por el servidor."""
    if isinstance(input_data.state, dict) and input_data.state.get("user_id"):
        return str(input_data.state["user_id"])
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo resolver la identidad del usuario autenticado.",
    )


session_service = DatabaseSessionService(db_url=SESSION_DB_URL)
memory_service = InMemoryMemoryService()

adk_ag_ui_agent = ADKAgent(
    adk_agent=root_agent,
    app_name="expense_approval_app",
    user_id_extractor=_resolve_user_id,
    session_service=session_service,
    memory_service=memory_service,
    use_in_memory_services=False,
    allow_scoped_state_keys=True,
    session_timeout_seconds=3600,
)

app = FastAPI(
    title="Expense Approval Agent (AG-UI + Google ADK 2.0)",
    version="0.2.0",
)

allowed_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok", "agent": root_agent.name}


@app.post("/auth/register", status_code=status.HTTP_201_CREATED)
async def auth_register(body: RegisterRequest) -> Dict[str, Any]:
    try:
        user = register_user(
            email=body.email,
            password=body.password,
            nombre=body.nombre,
            rol=body.rol,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    token = create_access_token(user)
    return {"access_token": token, "token_type": "bearer", "user": user}


@app.post("/auth/login")
async def auth_login(body: LoginRequest) -> Dict[str, Any]:
    try:
        user = login_user(email=body.email, password=body.password)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    token = create_access_token(user)
    return {"access_token": token, "token_type": "bearer", "user": user}


@app.get("/auth/me")
async def auth_me(user: Dict[str, Any] = Depends(require_authenticated_user)) -> Dict[str, Any]:
    return {"user": user}


# Expone el protocolo AG-UI protegido por Bearer JWT + inyección de estado confiable
add_adk_fastapi_endpoint(
    app,
    adk_ag_ui_agent,
    path="/",
    extract_state_from_request=extract_verified_user_state,
    dependencies=[Depends(require_authenticated_user)],
)


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host=host, port=port)
