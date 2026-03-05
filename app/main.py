"""
app/main.py
Factory de la aplicación FastAPI.
Configura CORS, middleware, routers y handlers de excepciones.
"""

import asyncio
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.api.routes.identify import router as identify_router
from app.services.pokemon_matcher import get_all_pokemon_names

# ── Logging ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Lifespan (startup / shutdown) ───────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Precarga el modelo ViT y el catálogo de Pokémon al arrancar.
    Ambos se cargan en paralelo para minimizar el tiempo de startup.
    """
    from app.services.vit_classifier import preload_model

    logger.info("🚀 Iniciando Pokemon Identifier API (Hybrid)...")

    # Cargar modelo ViT y catálogo Pokémon en paralelo
    logger.info("⚡ Cargando modelo ViT y catálogo Pokémon en paralelo...")
    vit_ok, pokemon_names = await asyncio.gather(
        preload_model(),
        get_all_pokemon_names(),
        return_exceptions=True,
    )

    if isinstance(vit_ok, Exception) or not vit_ok:
        logger.warning(
            "⚠  Modelo ViT no disponible. Se usará solo Gemini como fallback."
        )
    else:
        logger.info(f"✅ Modelo ViT listo: {settings.VIT_MODEL_ID}")

    if isinstance(pokemon_names, Exception):
        logger.warning(
            "⚠  Catálogo Pokémon no precargado. Se cargará en la primera petición."
        )
    else:
        logger.info(f"✅ Catálogo listo: {len(pokemon_names)} Pokémon")

    logger.info(f"🌐 CORS habilitado para: {settings.ALLOWED_ORIGINS}")
    logger.info("✅ API lista para recibir peticiones")

    # Iniciar watcher de inactividad en background
    from app.services.vit_classifier import start_idle_watcher

    idle_task = asyncio.create_task(start_idle_watcher())

    yield

    idle_task.cancel()
    logger.info("🛑 Apagando Pokemon Identifier API...")


# ── App Factory ──────────────────────────────────────────────────────
def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="""
## 🎮 Pokemon Identifier API — Sistema Híbrido

Identifica Pokémon en imágenes combinando un **modelo ViT fine-tuneado** con
**Gemini 1.5 Flash** como fallback inteligente.

### Flujo de decisión
| Confianza ViT | Acción | Tiempo estimado |
|---|---|---|
| ≥ 80% | Respuesta directa del ViT | ~100ms |
| 40–80% | ViT + Gemini en paralelo, mejor resultado gana | ~1–2s |
| < 40% | Solo Gemini | ~1–2s |

### Autenticación
No requiere autenticación para el cliente. Las claves se configuran en el servidor.
        """,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── Middleware: CORS ─────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Process-Time"],
    )

    # ── Middleware: Compresión GZIP ──────────────────────────────────
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # ── Middleware: Tiempo de proceso ────────────────────────────────
    import time
    from fastapi import Request, Response

    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        start = time.perf_counter()
        response: Response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Process-Time"] = f"{duration_ms:.2f}ms"
        return response

    # ── Handlers de errores ──────────────────────────────────────────
    register_exception_handlers(app)

    # ── Routers ──────────────────────────────────────────────────────
    app.include_router(identify_router)

    return app


app = create_app()
