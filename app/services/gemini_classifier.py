"""
app/services/gemini_classifier.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Identificador de Pokémon usando Google Gemini 2.5 Flash.

Usa response_mime_type="application/json" para forzar JSON válido
directamente desde el SDK — elimina todos los problemas de parsing.

Optimizado para fotos del mundo real: juguetes, figuras, cartas,
fanart, capturas de pantalla y cualquier imagen de cámara.

Límites del tier gratuito de Google AI Studio:
 1,500 requests/día | 1,000,000 tokens/día | 15 req/minuto
"""

import json
import logging
import re
import asyncio
from typing import Optional

import google.generativeai as genai
from PIL import Image
import io

from app.core.config import settings

logger = logging.getLogger(__name__)

_model = None


def _get_model():
    """Singleton: configura y retorna el modelo Gemini con JSON mode activo."""
    global _model
    if _model is None:
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY no configurada.")
        genai.configure(api_key=settings.GEMINI_API_KEY)
        _model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            generation_config=genai.GenerationConfig(
                temperature=0,
                max_output_tokens=512,
                response_mime_type="application/json",
                response_schema={
                    "type": "object",
                    "properties": {
                        "pokemon_name": {"type": "string"},
                        "confidence": {"type": "integer"},
                        "reasoning": {"type": "string"}
                    },
                    "required": ["pokemon_name", "confidence"]
                },
            ),
        )
    return _model


PROMPT_TEMPLATE = """You are an expert Pokémon identifier that can recognize Pokémon
from any type of image: toys, figures, trading cards, screenshots, plushies, fanart,
or real-life photos of small figurines.

Analyze the image carefully and identify the Pokémon shown.

Return a JSON object with exactly these fields:
- "pokemon_name": official Pokémon name in lowercase with hyphens (e.g. "charizard", "mr-mime", "ho-oh"). Use null if no Pokémon found.
- "confidence": integer 0-100 representing your confidence level
- "reasoning": one sentence describing the visual features used to identify it{hint}"""


async def classify_with_gemini(
    image_bytes: bytes,
    vit_hint: Optional[str] = None,
) -> tuple[Optional[str], float]:
    """
    Identifica el Pokémon en la imagen usando Gemini 2.5 Flash con JSON mode.

    Returns:
        (pokemon_name | None, confidence 0-100)
    """
    if not settings.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY no configurada.")
        return None, 0.0

    model = _get_model()
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    raw = ""

    hint_text = ""
    if vit_hint:
        hint_text = (
            f"\n\nHint: a classifier weakly suggests '{vit_hint}' "
            f"— consider it but rely on your own visual analysis."
        )

    prompt = PROMPT_TEMPLATE.format(hint=hint_text)

    retry_delays = [1, 2, 4]

    for attempt in range(len(retry_delays) + 1):
        try:
            logger.info(f"Enviando imagen a Gemini 2.5 Flash (attempt {attempt + 1})...")
            response = await model.generate_content_async([prompt, image])

            if not response.candidates:
                logger.warning(f"Gemini response blocked (no candidates) at attempt {attempt + 1}")
                if attempt < len(retry_delays):
                    await asyncio.sleep(retry_delays[attempt])
                    continue
                return None, 0.0

            raw = response.text or ""
            if not raw:
                logger.warning(f"Gemini returned empty response at attempt {attempt + 1}")
                if attempt < len(retry_delays):
                    await asyncio.sleep(retry_delays[attempt])
                    continue

            logger.info(f"Gemini respuesta: {raw[:300]}")

            data = json.loads(raw)

            pokemon_name = data.get("pokemon_name")
            confidence = float(data.get("confidence", 0))
            reasoning = data.get("reasoning", "")

            if not pokemon_name or str(pokemon_name).lower() in ("null", "none", ""):
                logger.info("Gemini: no Pokémon encontrado en la imagen.")
                return None, 0.0

            name = _normalize_name(str(pokemon_name))
            if not name:
                return None, 0.0

            logger.info(f"Gemini → '{name}' ({confidence:.0f}%) — {reasoning}")
            return name, confidence

        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode error at attempt {attempt + 1}: {e}")
            if attempt < len(retry_delays):
                await asyncio.sleep(retry_delays[attempt])
                continue
            
            logger.warning(f"No se pudo parsear respuesta tras reintentos. Raw: {raw[:300] if raw else 'empty'}")
            return None, 0.0

        except Exception as e:
            error_msg = str(e)
            if "quota" in error_msg.lower() or "429" in error_msg:
                logger.error(f"Rate limit hit - stopping retries: {error_msg[:100]}")
                return None, 0.0
            
            if "safety_ratings" in error_msg or "Invalid operation" in error_msg:
                logger.warning(f"Gemini safety/rating block at attempt {attempt + 1}: {error_msg}")
                if attempt < len(retry_delays):
                    await asyncio.sleep(retry_delays[attempt])
                    continue
                return None, 0.0
            
            logger.warning(f"Error en Gemini: {e}")
            if attempt < len(retry_delays):
                await asyncio.sleep(retry_delays[attempt])
                continue
            return None, 0.0

    return None, 0.0


def _normalize_name(name: str) -> str:
    """
    Normaliza al formato PokéAPI.
    "Mr. Mime" -> "mr-mime" | "Farfetch'd" -> "farfetchd" | "Nidoran female" -> "nidoran-f"
    """
    if not name or name.lower() in ("null", "none", ""):
        return ""
    name = name.lower().strip()
    name = name.replace("\u2640", "-f").replace("\u2642", "-m")
    name = re.sub(r"[.'`'\u00b4:]", "", name)
    name = re.sub(r"[\s_]+", "-", name)
    name = re.sub(r"-+", "-", name)
    return name.strip("-")
