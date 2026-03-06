"""
app/models/schemas.py
Modelos Pydantic para las respuestas de la API.
"""

from pydantic import BaseModel, Field
from typing import Optional


class PokemonType(BaseModel):
    slot: int
    name: str


class PokemonStats(BaseModel):
    hp: int
    attack: int
    defense: int
    speed: int


class PokemonDetails(BaseModel):
    """Datos obtenidos de PokeAPI."""

    id: int
    name: str
    height: float = Field(..., description="Altura en metros")
    weight: float = Field(..., description="Peso en kilogramos")
    types: list[PokemonType]
    stats: PokemonStats
    sprite_url: Optional[str] = None
    pokeapi_url: str


class DetectionMethod:
    """Metodos de deteccion disponibles."""

    GEMINI_VISION = "gemini_vision"  # Gemini 2.5 Flash (motor principal)
    VIT_DIRECT = "vit_direct"  # Legacy
    VIT_FALLBACK = "vit_fallback"  # Legacy
    VIT_CONFIRMED = "vit_confirmed"  # Legacy
    GPT4O_VISION = "gpt4o_vision"  # Legacy


class IdentificationResult(BaseModel):
    """Respuesta exitosa del endpoint de identificacion."""

    success: bool = True
    pokemon_name: str = Field(..., description="Nombre del Pokemon identificado")
    confidence: float = Field(
        ..., ge=0.0, le=100.0, description="Porcentaje de confianza (0-100)"
    )
    detection_method: str = Field(..., description="Motor usado: gemini_vision")
    matched_keywords: list[str] = Field(
        default=[], description="Palabras clave (no usado)"
    )
    details: Optional[PokemonDetails] = Field(
        None, description="Datos del Pokemon de PokeAPI"
    )


class ErrorResponse(BaseModel):
    """Respuesta de error estandar."""

    success: bool = False
    error: str
