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
    """Datos básicos obtenidos de PokéAPI."""

    id: int
    name: str
    height: float = Field(..., description="Altura en metros")
    weight: float = Field(..., description="Peso en kilogramos")
    types: list[PokemonType]
    stats: PokemonStats
    sprite_url: Optional[str] = None
    pokeapi_url: str


class DetectionMethod(str):
    VIT_DIRECT = "vit_direct"  # ViT >= 80% — respuesta directa sin GPT-4o
    GPT4O_VISION = "gpt4o_vision"  # GPT-4o Vision — ViT < 80%, GPT-4o identificó
    VIT_FALLBACK = (
        "vit_fallback"  # GPT-4o falló, se usó resultado ViT como último recurso
    )
    # Legacy (mantenidos por compatibilidad con clientes existentes)
    VIT_CONFIRMED = "vit_confirmed"
    SERPAPI_FALLBACK = "serpapi_fallback"
    SERPAPI_ONLY = "serpapi_only"


class IdentificationResult(BaseModel):
    """Respuesta exitosa del endpoint de identificación."""

    success: bool = True
    pokemon_name: str = Field(..., description="Nombre del Pokémon identificado")
    confidence: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Porcentaje de confianza basado en la frecuencia de aparición en resultados",
    )
    detection_method: str = Field(
        ...,
        description="Método usado: vit_direct | vit_confirmed | serpapi_fallback | serpapi_only",
    )
    matched_keywords: list[str] = Field(
        default=[],
        description="Palabras clave que llevaron a la identificación (solo en métodos SerpAPI)",
    )
    details: Optional[PokemonDetails] = Field(
        None, description="Datos del Pokémon de PokéAPI (si está disponible)"
    )


class ErrorResponse(BaseModel):
    """Respuesta de error estándar."""

    success: bool = False
    error: str
