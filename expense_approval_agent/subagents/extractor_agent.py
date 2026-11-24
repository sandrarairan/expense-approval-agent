from google.adk.agents import LlmAgent

from ..schemas import ExpenseExtraction

# Sub-agente especializado únicamente en extracción estructurada (texto, PDF o imagen)
extractor_agent = LlmAgent(
    name="extractor",
    model="gemini-3.6-flash",
    description="Extrae datos estructurados de facturas, recibos o contratos (texto, PDF o imagen).",
    instruction="""
    Eres un extractor multimodal de facturas y contratos.
    Analiza tanto el texto como cualquier archivo adjunto (PDF o imagen de factura/recibo/contrato) en el mensaje del usuario.
    Extrae: concepto, monto numérico (usa siempre el TOTAL final con impuestos incluidos, no el subtotal), moneda, categoría y proveedor.
    Responde únicamente con los datos estructurados del esquema.
    """,
    output_schema=ExpenseExtraction,
    output_key="extracted_expense",  # (03a) Guarda la extracción estructurada en session.state
)
