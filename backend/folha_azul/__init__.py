"""OMR exclusivo — folha azul UCM (gabarito FOLHA AZUL1.pdf)."""
from folha_azul.leitor import (
    FASES_OMR,
    PROXIMA_FASE_OMR,
    normalizar_fase_omr,
    processar_folha_azul,
)

__all__ = [
    "FASES_OMR",
    "PROXIMA_FASE_OMR",
    "normalizar_fase_omr",
    "processar_folha_azul",
]
