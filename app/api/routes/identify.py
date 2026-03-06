"""
app/api/routes/identify.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTROLADOR PRINCIPAL — POST /api/identify-pokemon
Motor: Gemini 2.5 Flash (único)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  imagen → validación → Gemini 2.5 Flash → PokéAPI → JSON

  Gemini analiza directamente cualquier tipo de imagen:
  juguetes, figuras, cartas, fanart, sprites, capturas de pantalla.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import logging

from fastapi import APIRouter, File, UploadFile

from app.core.config import settings
from app.core.exceptions import PokemonNotFoundException
from app.models.schemas import IdentificationResult, ErrorResponse, DetectionMethod
from app.services.image_validator import validate_and_read_image
from app.services.gemini_classifier import classify_with_gemini
from app.services.pokeapi_service import fetch_pokemon_details

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Pokemon Identification"])


@router.post(
    "/identify-pokemon",
    response_model=IdentificationResult,
    responses={
        200: {
            "model": IdentificationResult,
            "description": "Pokémon identificado con éxito",
        },
        404: {"model": ErrorResponse, "description": "No se identificó ningún Pokémon"},
        413: {"model": ErrorResponse, "description": "Imagen demasiado grande"},
        422: {"model": ErrorResponse, "description": "Archivo inválido"},
    },
    summary="Identificar Pokémon a partir de una imagen",
    description="""
Recibe una imagen y devuelve el Pokémon usando **Gemini 2.5 Flash**.

Funciona con cualquier tipo de imagen: juguetes, figuras, cartas,
capturas de pantalla, fanart o fotos reales. Tier gratuito: 1,500 req/día.
    """,
)
async def identify_pokemon(
    file: UploadFile = File(
        ..., description="Imagen del Pokémon (JPEG, PNG, WEBP o GIF, máx. 5 MB)"
    ),
) -> IdentificationResult:

    # ── Paso 1: Validar imagen ────────────────────────────────────────
    logger.info(f"[INICIO] Procesando: {file.filename} ({file.content_type})")
    image_bytes = await validate_and_read_image(file)
    logger.info(f"[1/2] ✓ Imagen válida — {len(image_bytes) / 1024:.1f} KB")

    # ── Paso 2: Identificar con Gemini ───────────────────────────────
    logger.info("[2/2] Identificando con Gemini 2.5 Flash...")
    pokemon_name, confidence = await classify_with_gemini(image_bytes)

    if not pokemon_name or confidence < settings.MIN_CONFIDENCE_THRESHOLD:
        logger.warning(
            f"[FIN] ✗ No identificado — '{pokemon_name}' al {confidence:.1f}%"
        )
        raise PokemonNotFoundException()

    # ── Paso 3: Enriquecer con PokéAPI ───────────────────────────────
    logger.info(f"[3/3] Obteniendo detalles de '{pokemon_name}'...")
    details = await fetch_pokemon_details(pokemon_name)

    if details:
        types = ", ".join(t.name for t in details.types)
        logger.info(f"      ✓ #{details.id} {details.name} [{types}]")

    logger.info(f"[FIN] ✅ '{pokemon_name}' con {confidence:.1f}% confianza")

    return IdentificationResult(
        success=True,
        pokemon_name=pokemon_name,
        confidence=confidence,
        detection_method=DetectionMethod.GEMINI_VISION,
        matched_keywords=[],
        details=details,
    )


@router.get("/health", summary="Health check", tags=["System"])
async def health_check() -> dict:
    return {
        "status": "ok",
        "service": "Pokemon Identifier API (Gemini 2.5 Flash)",
        "gemini_configured": bool(settings.GEMINI_API_KEY),
        "min_confidence": f"{settings.MIN_CONFIDENCE_THRESHOLD}%",
    }
