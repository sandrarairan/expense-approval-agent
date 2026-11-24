# Expense Approval Agent (Google ADK 2.0 + AG-UI + CopilotKit v2)

Agente multi-usuario de aprobación de gastos y contratos construido con **Google ADK 2.0**, protocolo **AG-UI** y frontend **Next.js + CopilotKit v2**:
- **Autenticación multi-usuario** (`auth.py` + `ag_ui_server.py`): registro y login real con contraseñas hasheadas (`scrypt`) en SQLite y tokens **JWT (HS256)** verificados antes de tocar el LLM.
- **Extracción multimodal** (`extractor_agent`): lee texto, PDFs o imágenes de facturas/contratos con `output_schema` (Pydantic).
- **Validación determinista** (`rules.py`): reglas de negocio en Python puro (sin LLM) con límites automáticos por rol (`empleado`, `gerente`, `director`).
- **Human-in-the-Loop (HITL)**: montos dentro del límite del rol se auto-aprueban; montos que superan el umbral pausan el flujo hasta confirmación humana.
- **Persistencia local** (`SQLite`): App DB (`expenses_app.db` con tablas `users` y `expenses`) separada del estado de sesión (`expense_sessions.db` vía `DatabaseSessionService`).
- **Frontend CopilotKit v2** (`frontend/`): app Next.js con pantalla de Login/Registro, BFF en `/api/copilotkit` y chat conectado vía AG-UI.
- **Evaluación**: listo para `adk eval` (`expense_approval_agent/evals/`) y `agents-cli eval` (`tests/eval/`).

## Arquitectura

```mermaid
flowchart TD
    Start(["Usuario en Next.js + CopilotKit v2<br/>Login / Registro + Chat de gastos"])

    subgraph Frontend["Frontend · Next.js + CopilotKit v2"]
        LoginUI["Login / Registro<br/>POST /api/auth/login · /api/auth/register"]
        BffRoute["BFF CopilotRuntime v2<br/>/api/copilotkit valida Bearer JWT y reenvía header"]
    end

    subgraph AuthEntry["Gatekeeper · FastAPI AG-UI + auth.py"]
        Auth["authenticate_token - JWT HS256<br/>Lee rol y límite desde SQLite users<br/>Inyecta user:id, user:rol y user:limite_aprobacion"]
        Router["recibir_entrada<br/>Revisa workflow_step y gasto_actual en session.state"]
        IsHitl{"¿Respuesta HITL<br/>pendiente?"}
    end

    subgraph Extractor["Extractor · extractor_agent - LlmAgent"]
        LlmExtract["gemini-3.6-flash<br/>Extrae concepto, monto, moneda, categoría y proveedor"]
        Schema["ExpenseExtraction - Pydantic<br/>Guarda extracted_expense en session.state"]
    end

    subgraph Rules["Validador · rules.py - Python puro"]
        CheckAmount{"¿Monto > 0?"}
        CheckCurrency{"¿Moneda permitida?<br/>USD, EUR, MXN, COP"}
        CheckLimit{"¿Monto <= umbral<br/>del rol?"}
    end

    subgraph HITL["Human-in-the-Loop - HITL"]
        AskHuman["solicitar_aprobacion<br/>Muestra resumen y pausa<br/>workflow_step = requiere_humano"]
        ProcessHuman["procesar_aprobacion_humana<br/>Lee gasto_actual sin re-llamar al LLM"]
        IsApproved{"¿Humano aprueba?"}
    end

    subgraph Persistence["Persistencia · Dual-Write SQLite"]
        ApproveNode["registrar<br/>Aprobación automática o humana<br/>Actualiza user:total_gastos_aprobados"]
        RejectNode["rechazar<br/>Registra motivo del rechazo<br/>workflow_step = rechazado"]
        AppDB[("expenses_app.db<br/>Tablas users y expenses")]
        SessionDB[("expense_sessions.db<br/>DatabaseSessionService + State")]
    end

    Start --> LoginUI --> BffRoute --> Auth --> Router --> IsHitl

    Auth -.-> AppDB

    IsHitl -->|"NO - nuevo_gasto"| LlmExtract
    LlmExtract --> Schema --> CheckAmount

    CheckAmount -->|"NO - rechazado"| RejectNode
    CheckAmount -->|"SÍ"| CheckCurrency
    CheckCurrency -->|"NO - requiere_humano"| AskHuman
    CheckCurrency -->|"SÍ"| CheckLimit
    CheckLimit -->|"SÍ - auto_aprobado"| ApproveNode
    CheckLimit -->|"NO - requiere_humano"| AskHuman

    AskHuman -.->|"Siguiente turno:<br/>aprobar o rechazar"| Router
    IsHitl -->|"SÍ - responder_aprobacion"| ProcessHuman
    ProcessHuman --> IsApproved
    IsApproved -->|"SÍ - aprobado"| ApproveNode
    IsApproved -->|"NO - rechazado"| RejectNode

    ApproveNode -.-> AppDB
    ApproveNode -.-> SessionDB
    RejectNode -.-> AppDB
    RejectNode -.-> SessionDB

    classDef startStyle fill:#f1f2fb,stroke:#2c3e50,stroke-width:2px,color:#1a202c
    classDef actionStyle fill:#ffffff,stroke:#2c3e50,stroke-width:1.5px,color:#1a202c
    classDef decisionStyle fill:#ffffff,stroke:#2c3e50,stroke-width:1.5px,color:#1a202c
    classDef hitlStyle fill:#fef9e7,stroke:#b7791f,stroke-width:1.5px,color:#744210
    classDef successStyle fill:#eafaf1,stroke:#1e8449,stroke-width:2px,color:#145a32
    classDef errorStyle fill:#fdecef,stroke:#c93b5b,stroke-width:2px,color:#9b1c31
    classDef dbStyle fill:#edf2f7,stroke:#4a5568,stroke-width:1.5px,color:#2d3748

    class Start startStyle
    class LoginUI,BffRoute,Auth,Router,LlmExtract,Schema,ProcessHuman actionStyle
    class IsHitl,CheckAmount,CheckCurrency,CheckLimit,IsApproved decisionStyle
    class AskHuman hitlStyle
    class ApproveNode successStyle
    class RejectNode errorStyle
    class AppDB,SessionDB dbStyle

    style Frontend fill:#ffffff,stroke:#b82952,stroke-width:2px,stroke-dasharray: 6 4,color:#2c3e50
    style AuthEntry fill:#ffffff,stroke:#b82952,stroke-width:2px,stroke-dasharray: 6 4,color:#2c3e50
    style Extractor fill:#ffffff,stroke:#b82952,stroke-width:2px,stroke-dasharray: 6 4,color:#2c3e50
    style Rules fill:#ffffff,stroke:#b82952,stroke-width:2px,stroke-dasharray: 6 4,color:#2c3e50
    style HITL fill:#ffffff,stroke:#b82952,stroke-width:2px,stroke-dasharray: 6 4,color:#2c3e50
    style Persistence fill:#ffffff,stroke:#b82952,stroke-width:2px,stroke-dasharray: 6 4,color:#2c3e50
```

## Instalación

### 1. Backend Python
```bash
uv venv
uv pip install --only-binary cryptography -e .
```

Copia `.env.example` a `expense_approval_agent/.env` (o `.env` en la raíz) y configura tus variables:
```env
GOOGLE_GENAI_USE_VERTEXAI=0
GOOGLE_API_KEY=tu_api_key_de_gemini
JWT_SECRET=clave_aleatoria_larga
```
Puedes generar `JWT_SECRET` con:
```bash
openssl rand -hex 32
```

### 2. Frontend Next.js (`frontend/`)
```bash
cd frontend
npm install
```

## Autenticación, Roles y Endpoints

La tabla `users` en `expense_approval_agent/expenses_app.db` almacena múltiples usuarios con contraseña hasheada (`scrypt`) y límite automático según el rol:

| Rol | Límite de auto-aprobación | Si el monto supera el límite |
| :--- | :--- | :--- |
| `empleado` | `<= 1,000` | Pausa HITL (`requiere_humano`) |
| `gerente` | `<= 5,000` | Pausa HITL (`requiere_humano`) |
| `director` | `<= 15,000` | Pausa HITL (`requiere_humano`) |

**Cuentas de prueba precargadas** (contraseña `demo1234`):
- `ana@empresa.com` (`empleado`, límite `<= 1,000`)
- `carlos@empresa.com` (`gerente`, límite `<= 5,000`)

**Endpoints expuestos por `ag_ui_server.py` (`http://localhost:8000`):**
- `POST /auth/register` — crea un usuario nuevo y devuelve `access_token` (JWT HS256).
- `POST /auth/login` — valida credenciales y devuelve `access_token` (JWT HS256).
- `GET /auth/me` — devuelve el perfil del usuario autenticado.
- `POST /` — endpoint AG-UI protegido con `Authorization: Bearer <jwt>` y `allow_scoped_state_keys=True`.
- `GET /health` — estado del servidor.

## Cómo ejecutar

### 1. App completa: Backend AG-UI + Frontend CopilotKit v2 (recomendado)

**Terminal 1 — Backend Python AG-UI (`http://localhost:8000`):**
```bash
.venv/bin/python -m expense_approval_agent.ag_ui_server
```

**Terminal 2 — Frontend Next.js (`http://localhost:3000`):**
```bash
cd frontend
npm run dev
```
Abre `http://localhost:3000`, inicia sesión con una cuenta precargada o crea una cuenta nueva desde la pestaña **Crear cuenta**.

### 2. Interfaz web de ADK (`adk web`)
```bash
.venv/bin/adk web
```
Abre `http://localhost:8000` y selecciona `expense_approval_agent`.

### 3. Ejecución por script con persistencia SQLite y memoria
```bash
.venv/bin/python -m expense_approval_agent.run_with_persistence
```

### 4. Evaluación (`adk eval`)
```bash
.venv/bin/adk eval expense_approval_agent expense_approval_agent/evals/expense_approval.evalset.json \
  --config_file_path=expense_approval_agent/evals/eval_config.json \
  --print_detailed_results
```
