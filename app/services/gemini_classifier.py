"""
app/services/gemini_classifier.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Identificador de Pokémon usando Google Gemini 1.5 Flash como fallback.

Ventajas:
 • 100% gratuito hasta 1,500 requests/día (más que suficiente)
 • Entiende fotos reales, figuras, cartas, fanart, capturas de pantalla
 • ~1–2s de latencia (más rápido que GPT-4o)
 • Respuesta directa con el nombre del Pokémon en formato PokéAPI

Límites del tier gratuito:
 • 1,500 requests/día
 • 1,000,000 tokens/día
 • 15 requests/minuto
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import json
import logging
import re
from typing import Optional

import google.generativeai as genai
from PIL import Image
import io

from app.core.config import settings

logger = logging.getLogger(__name__)

_model = None
_semaphore = asyncio.Semaphore(15)


def _get_model():
    """Retorna el modelo Gemini configurado (singleton)."""
    global _model
    if _model is None:
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY no está configurada.")
        genai.configure(api_key=settings.GEMINI_API_KEY)
        _model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config=genai.GenerationConfig(
                temperature=0,  # determinístico
                max_output_tokens=150,  # la respuesta JSON es corta
            ),
        )
    return _model


# ── Prompt ───────────────────────────────────────────────────────────

PROMPT_TEMPLATE = """You are a Pokémon identification expert.
Identify the Pokémon in this image and respond ONLY with a valid JSON object:
{{
  "pokemon_name": "name-in-lowercase-with-hyphens",
  "confidence": 85,
  "reasoning": "brief explanation"
}}

Rules:
- pokemon_name must be the official name in lowercase with hyphens (e.g. "mr-mime", "ho-oh", "charizard")
- confidence is an integer 0-100
- If no Pokémon is visible or you are not sure, set pokemon_name to null and confidence to 0
- Respond ONLY with the JSON, no extra text{hint}"""


async def classify_with_gemini(
    image_bytes: bytes,
    vit_hint: Optional[str] = None,
) -> tuple[Optional[str], float]:
    """
    Identifica el Pokémon en la imagen usando Gemini 1.5 Flash.

    Args:
        image_bytes: Contenido binario de la imagen.
        vit_hint: Sugerencia del modelo ViT (mejora la precisión de Gemini).

    Returns:
        (pokemon_name | None, confidence 0–100)
    """
    if not settings.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY no configurada. Gemini no disponible.")
        return None, 0.0

    try:
        model = _get_model()

        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        hint_text = ""
        if vit_hint:
            hint_text = (
                f"\n\nNote: a vision classifier suggests it might be '{vit_hint}' "
                f"but had low confidence — verify visually and correct if needed."
            )

        prompt = PROMPT_TEMPLATE.format(hint=hint_text)

        logger.info("Enviando imagen a Gemini 1.5 Flash...")

        async with _semaphore:
            response = await asyncio.wait_for(
                model.generate_content_async([prompt, image]),
                timeout=30.0,
            )

        raw = response.text or ""
        logger.info(f"Gemini respuesta raw: {raw[:200]}")

        clean = re.sub(r"```(?:json)?|```", "", raw).strip()
        data = json.loads(clean)

        pokemon_name = data.get("pokemon_name")
        confidence = float(data.get("confidence", 0))
        reasoning = data.get("reasoning", "")

        if not pokemon_name:
            logger.info("Gemini: no se encontró Pokémon en la imagen.")
            return None, 0.0

        name = _normalize_name(pokemon_name)
        logger.info(f"Gemini → '{name}' ({confidence:.0f}%) — {reasoning}")

        return name, confidence

    except asyncio.TimeoutError:
        logger.warning("Gemini: timeout de 30s excedido.")
        return None, 0.0
    except json.JSONDecodeError as e:
        raw = getattr(response, 'text', '') if 'response' in dir() else ""
        logger.warning(f"Gemini respuesta no es JSON válido: {e}. Raw: {raw[:300]}")
        return None, 0.0
    except Exception as e:
        logger.warning(f"Error en Gemini Flash: {e}")
        return None, 0.0


def _normalize_name(name: str) -> str:
    """
    Normaliza el nombre al formato de PokéAPI.
    "Mr. Mime" → "mr-mime" | "Farfetch'd" → "farfetchd" | "Nidoran♀" → "nidoran-f"
    """
    name = name.lower().strip()
    name = name.replace("\u2640", "-f").replace("\u2642", "-m")
    name = re.sub(r"[.'`':]", "", name)
    name = re.sub(r"[\s\-]+", "-", name)
    return name.strip("-")
