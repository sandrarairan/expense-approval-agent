# Expense Approval Agent (Google ADK 2.0)

Agente de aprobación de gastos y contratos construido con **Google ADK 2.0**:
- **Extracción multimodal** (`extractor_agent`): lee texto, PDFs o imágenes de facturas/contratos con `output_schema` (Pydantic).
- **Validación determinista** (`rules.py`): reglas de negocio en Python puro (sin LLM) con límites por rol.
- **Human-in-the-Loop (HITL)**: montos pequeños se auto-aprueban; montos que superan el umbral pausan el flujo hasta confirmación humana.
- **Persistencia local** (`SQLite`): App DB (`expenses_app.db`) separada del estado de sesión (`DatabaseSessionService`).
- **Evaluación**: listo para `adk eval` (`expense_approval_agent/evals/`) y `agents-cli eval` (`tests/eval/`).

## Arquitectura

```mermaid
flowchart TD
    Start(["Entrada del usuario<br/>Texto, PDF o imagen + Token Auth"])

    subgraph AuthEntry["Gatekeeper · Autenticación y Entrada"]
        Auth["authenticate_token<br/>Inyecta user:id, user:rol y user:limite_aprobacion"]
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
        AppDB[("expenses_app.db<br/>Tabla expenses - auditoría")]
        SessionDB[("expense_sessions.db<br/>DatabaseSessionService + State")]
    end

    Start --> Auth --> Router --> IsHitl

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
    class Auth,Router,LlmExtract,Schema,ProcessHuman actionStyle
    class IsHitl,CheckAmount,CheckCurrency,CheckLimit,IsApproved decisionStyle
    class AskHuman hitlStyle
    class ApproveNode successStyle
    class RejectNode errorStyle
    class AppDB,SessionDB dbStyle

    style AuthEntry fill:#ffffff,stroke:#b82952,stroke-width:2px,stroke-dasharray: 6 4,color:#2c3e50
    style Extractor fill:#ffffff,stroke:#b82952,stroke-width:2px,stroke-dasharray: 6 4,color:#2c3e50
    style Rules fill:#ffffff,stroke:#b82952,stroke-width:2px,stroke-dasharray: 6 4,color:#2c3e50
    style HITL fill:#ffffff,stroke:#b82952,stroke-width:2px,stroke-dasharray: 6 4,color:#2c3e50
    style Persistence fill:#ffffff,stroke:#b82952,stroke-width:2px,stroke-dasharray: 6 4,color:#2c3e50
```

## Instalación

```bash
uv venv
uv pip install --only-binary cryptography -e .
```

Copia `.env.example` a `expense_approval_agent/.env` y agrega tu `GOOGLE_API_KEY`.

## Cómo ejecutar

### 1. Interfaz web (`adk web`)
```bash
.venv/bin/adk web
```
Abre `http://localhost:8000` y selecciona `expense_approval_agent`.

### 2. Ejecución por código con autenticación externa, SQLite y memoria
```bash
.venv/bin/python -m expense_approval_agent.run_with_persistence
```

### 3. Evaluación (`adk eval`)
```bash
.venv/bin/adk eval expense_approval_agent expense_approval_agent/evals/expense_approval.evalset.json \
  --config_file_path=expense_approval_agent/evals/eval_config.json \
  --print_detailed_results
```
