"""
app/services/vit_classifier.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Clasificador ViT con lazy loading + auto-descarga por inactividad.

Optimizado para Railway (Escenario 2: ~200 req/día, 6h activas):
 • El modelo se carga cuando llega la primera request
 • Se descarga automáticamente tras 5 min sin uso (configurable)
 • Esto evita acumular RAM durante las horas sin tráfico
 • Carga + descarga es thread-safe con doble lock
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import gc
import io
import logging
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from PIL import Image

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Estado del modelo ────────────────────────────────────────────────
_classifier = None
_model_lock = threading.Lock()
_last_used: float = 0.0
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="vit_worker")

# Tiempo de inactividad antes de descargar el modelo (segundos)
_IDLE_TIMEOUT: int = int(os.getenv("VIT_IDLE_TIMEOUT", 300))


# ── Carga ────────────────────────────────────────────────────────────


def _load_model_sync():
    """Carga el pipeline. Sincrono, corre en ThreadPoolExecutor."""
    global _classifier

    from transformers import pipeline
    import torch

    device = 0 if torch.cuda.is_available() else -1
    device_name = "GPU (CUDA)" if device == 0 else "CPU"

    logger.info(f"Cargando modelo ViT en {device_name}...")
    t0 = time.perf_counter()

    _classifier = pipeline(
        task="image-classification",
        model=settings.VIT_MODEL_ID,
        device=device,
    )

    elapsed = (time.perf_counter() - t0) * 1000
    logger.info(f"Modelo ViT listo ({elapsed:.0f}ms)")
    return _classifier


def _get_or_load_classifier():
    """Retorna el clasificador, carganadolo si no esta en memoria. Thread-safe."""
    global _classifier, _last_used

    _last_used = time.time()

    if _classifier is None:
        with _model_lock:
            if _classifier is None:
                _load_model_sync()

    return _classifier


# ── Descarga por inactividad ─────────────────────────────────────────


def _unload_model_if_idle():
    """Descarga el modelo si lleva mas de _IDLE_TIMEOUT segundos sin usarse."""
    global _classifier, _last_used

    if _classifier is None:
        return

    idle_seconds = time.time() - _last_used
    if idle_seconds < _IDLE_TIMEOUT:
        return

    with _model_lock:
        if _classifier is None:
            return
        if (time.time() - _last_used) < _IDLE_TIMEOUT:
            return

        logger.info(
            f"Modelo ViT inactivo {idle_seconds:.0f}s. "
            "Descargando para liberar RAM..."
        )
        del _classifier
        _classifier = None
        gc.collect()

        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

        logger.info("Modelo descargado. RAM liberada.")


async def start_idle_watcher():
    """Tarea de fondo: revisa inactividad cada 60 segundos."""
    logger.info(f"Idle watcher iniciado (timeout: {_IDLE_TIMEOUT}s)")
    try:
        while True:
            await asyncio.sleep(60)
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, _unload_model_if_idle)
            except Exception as e:
                logger.warning(f"Idle watcher error: {e}")
    except asyncio.CancelledError:
        logger.info("Idle watcher cancelado.")


# ── Inferencia ───────────────────────────────────────────────────────


def _run_inference_sync(image_bytes: bytes) -> list[dict]:
    """Inferencia sincrona. Corre en ThreadPoolExecutor."""
    classifier = _get_or_load_classifier()
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    return classifier(image, top_k=3)


async def classify_with_vit(
    image_bytes: bytes,
) -> tuple[Optional[str], float, bool]:
    """
    Clasifica la imagen con el modelo ViT de forma asincrona.

    Returns:
        (pokemon_name | None, confidence %, is_reliable)
    """
    if not settings.VIT_ENABLED:
        logger.info("ViT deshabilitado (VIT_ENABLED=false). Usando SerpAPI.")
        return None, 0.0, False

    try:
        loop = asyncio.get_event_loop()
        results: list[dict] = await loop.run_in_executor(
            _executor,
            _run_inference_sync,
            image_bytes,
        )

        if not results:
            return None, 0.0, False

        best = results[0]
        pokemon_name = _normalize_pokemon_name(best["label"])
        confidence = round(best["score"] * 100, 2)

        logger.info("ViT Top 3:")
        for r in results:
            n = _normalize_pokemon_name(r["label"])
            s = round(r["score"] * 100, 2)
            marker = "<- elegido" if n == pokemon_name else ""
            logger.info(f"   {n:<20} {s:>6.2f}%  {marker}")

        is_reliable = confidence >= settings.VIT_CONFIDENCE_THRESHOLD
        return pokemon_name, confidence, is_reliable

    except Exception as e:
        logger.warning(f"Error en ViT: {e}. Activando fallback SerpAPI.")
        return None, 0.0, False


# ── Precarga (opcional al startup) ───────────────────────────────────


async def preload_model() -> bool:
    """Precarga el modelo al arrancar. Retorna True si tiene exito."""
    if not settings.VIT_ENABLED:
        return False
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(_executor, _get_or_load_classifier)
        return True
    except Exception as e:
        logger.error(f"No se pudo precargar el modelo ViT: {e}")
        return False


# ── Normalizacion de nombres ─────────────────────────────────────────


def _normalize_pokemon_name(label: str) -> str:
    """Convierte el label del modelo al formato de PokeAPI."""
    name = label.lower().strip()
    name = name.replace("\u2640", "-f").replace("\u2642", "-m")
    name = re.sub(r"[.'`']", "", name)
    name = re.sub(r"[\s\-]+", "-", name)
    return name.strip("-")
