"""
app/api/routes/identify.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTROLADOR PRINCIPAL — POST /api/identify-pokemon
Sistema híbrido ViT + Gemini Flash
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Lógica de decisión:

  imagen
    │
  [ViT classifier]
    │
    ├── score >= 80% ──→  VIT_DIRECT (~100ms)
    │                     Respuesta directa, sin llamar a Gemini
    │
    └── score <  80% ──→  [Gemini Flash] (~2–4s)
                          Entiende fotos reales, figuras, cartas,
                          fanart y cualquier imagen del mundo real
                          │
                          ├── Gemini responde → GEMINI_VISION
                          └── Gemini falla    → VIT_FALLBACK (usa ViT de todos modos)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import logging

from fastapi import APIRouter, File, UploadFile

from app.core.config import settings
from app.core.exceptions import PokemonNotFoundException
from app.models.schemas import IdentificationResult, ErrorResponse, DetectionMethod
from app.services.image_validator import validate_and_read_image
from app.services.vit_classifier import classify_with_vit
from app.services.gemini_classifier import classify_with_gemini
from app.services.pokeapi_service import fetch_pokemon_details

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Pokemon Identification"])


# ────────────────────────────────────────────────────────────────────
# ENDPOINT PRINCIPAL
# ────────────────────────────────────────────────────────────────────


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
        503: {
            "model": ErrorResponse,
            "description": "Servicios externos no disponibles",
        },
    },
    summary="Identificar Pokémon a partir de una imagen",
    description="""
Recibe una imagen y devuelve el Pokémon mediante un **sistema híbrido ViT + Gemini 2.5 Flash**.

**Flujo:**
- ViT supera **80%** → respuesta directa (~100ms)
- ViT bajo **80%** → Gemini 1.5 Flash analiza la imagen (~1–2s)

Gemini Flash entiende fotos reales, figuras, cartas, fanart y cualquier imagen del mundo real. Tier gratuito: 1,500 requests/día.
    """,
)
async def identify_pokemon(
    file: UploadFile = File(
        ..., description="Imagen del Pokémon (JPEG, PNG, WEBP o GIF, máx. 5 MB)"
    ),
) -> IdentificationResult:

    # ─────────────────────────────────────────────────────────────────
    # PASO 1: Validar imagen
    # ─────────────────────────────────────────────────────────────────
    logger.info(f"[INICIO] Procesando: {file.filename} ({file.content_type})")
    image_bytes = await validate_and_read_image(file)
    logger.info(f"[1/4] ✓ Imagen válida — {len(image_bytes) / 1024:.1f} KB")

    # ─────────────────────────────────────────────────────────────────
    # PASO 2: Clasificación con ViT
    # ─────────────────────────────────────────────────────────────────
    logger.info("[2/4] Clasificando con modelo ViT...")
    vit_name, vit_confidence, vit_is_reliable = await classify_with_vit(image_bytes)
    logger.info(
        f"      ViT → '{vit_name}' {vit_confidence:.1f}% "
        f"({'confiable ✓' if vit_is_reliable else 'baja confianza — activando Gemini ⚡'})"
    )

    # ─────────────────────────────────────────────────────────────────
    # PASO 3: Decisión ViT vs Gemini
    # ─────────────────────────────────────────────────────────────────
    final_name: str | None = None
    final_confidence: float = 0.0
    final_method: str = DetectionMethod.VIT_DIRECT

    # ── Rama A: ViT con alta confianza → respuesta directa ──────────
    if vit_name and vit_is_reliable:
        logger.info(
            f"[3/4] ✅ VIT_DIRECT — {vit_confidence:.1f}% >= {settings.VIT_CONFIDENCE_THRESHOLD}%"
        )
        final_name = vit_name
        final_confidence = vit_confidence
        final_method = DetectionMethod.VIT_DIRECT

    # ── Rama B: ViT inseguro → Gemini Flash ────────────────────────
    else:
        logger.info(f"[3/4] ⚡ Activando Gemini Flash (ViT: {vit_confidence:.1f}%)...")

        # Pasamos el hint del ViT a Gemini para mejorar precisión
        gpt_name, gpt_confidence = await classify_with_gemini(
            image_bytes,
            vit_hint=vit_name,
        )

        if gpt_name and gpt_confidence > 0:
            logger.info(f"      Gemini → '{gpt_name}' ({gpt_confidence:.1f}%)")
            final_name = gpt_name
            final_confidence = gpt_confidence
            final_method = DetectionMethod.GEMINI_VISION

        elif vit_name and vit_confidence > 0:
            # Gemini falló — usamos el ViT como último recurso
            logger.warning(
                f"      Gemini falló. Usando resultado ViT como fallback: '{vit_name}'"
            )
            final_name = vit_name
            final_confidence = vit_confidence
            final_method = DetectionMethod.VIT_FALLBACK

    # ── Umbral mínimo global ─────────────────────────────────────────
    if not final_name or final_confidence < settings.MIN_CONFIDENCE_THRESHOLD:
        logger.warning(
            f"[FIN] ✗ No identificado. Mejor resultado: '{final_name}' al {final_confidence:.1f}%"
        )
        raise PokemonNotFoundException()

    # ─────────────────────────────────────────────────────────────────
    # PASO 4: Detalles desde PokéAPI
    # ─────────────────────────────────────────────────────────────────
    logger.info(f"[4/4] Obteniendo detalles de '{final_name}'...")
    details = await fetch_pokemon_details(final_name)

    if details:
        types = ", ".join(t.name for t in details.types)
        logger.info(f"      ✓ #{details.id} {details.name} [{types}]")

    logger.info(
        f"[FIN] ✅ '{final_name}' via {final_method} con {final_confidence:.1f}% confianza"
    )

    return IdentificationResult(
        success=True,
        pokemon_name=final_name,
        confidence=final_confidence,
        detection_method=final_method,
        matched_keywords=[],
        details=details,
    )


# ────────────────────────────────────────────────────────────────────
# HEALTH CHECK
# ────────────────────────────────────────────────────────────────────


@router.get("/health", summary="Health check", tags=["System"])
async def health_check() -> dict:
    """Estado del servicio y sus dependencias."""
    from app.services.vit_classifier import _classifier

    return {
        "status": "ok",
        "service": "Pokemon Identifier API (ViT + Gemini Flash)",
        "vit_model_loaded": _classifier is not None,
        "vit_model_id": settings.VIT_MODEL_ID,
        "gemini_configured": bool(settings.GEMINI_API_KEY),
        "thresholds": {
            "vit_direct": f"{settings.VIT_CONFIDENCE_THRESHOLD}%",
            "min_global": f"{settings.MIN_CONFIDENCE_THRESHOLD}%",
        },
    }
