from typing import Literal, Optional
from pydantic import BaseModel, Field


class ExpenseExtraction(BaseModel):
    """Datos estructurados extraídos de una factura, recibo o contrato."""

    concepto: str = Field(
        description="Descripción breve del gasto o contrato (ej. 'Licencia software', 'Vuelo a Madrid')."
    )
    monto: float = Field(
        description="Monto numérico total con impuestos incluidos, sin símbolo de moneda (ej. 250.0, 4500.0)."
    )
    moneda: str = Field(
        default="USD",
        description="Código de moneda de 3 letras (ej. 'USD', 'EUR', 'COP', 'MXN').",
    )
    categoria: Literal["viajes", "software", "hardware", "servicios", "otro"] = Field(
        default="otro",
        description="Categoría del gasto o contrato.",
    )
    proveedor: Optional[str] = Field(
        default=None,
        description="Nombre del proveedor o empresa emisora, si aparece.",
    )


class ValidationResult(BaseModel):
    """Resultado determinista de las reglas de negocio."""

    expense: ExpenseExtraction
    aprobacion_automatica: bool
    motivo: str
