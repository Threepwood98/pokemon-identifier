"""
app/main.py
Factory de la aplicación FastAPI.
"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.api.routes.identify import router as identify_router

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Iniciando Pokemon Identifier API (Gemini 2.5 Flash)...")
    logger.info(f"🌐 CORS habilitado para: {settings.ALLOWED_ORIGINS}")

    if settings.GEMINI_API_KEY:
        logger.info("✅ Gemini API key configurada")
    else:
        logger.warning("⚠  GEMINI_API_KEY no configurada — las requests fallarán")

    logger.info("✅ API lista para recibir peticiones")
    yield
    logger.info("🛑 Apagando Pokemon Identifier API...")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="""
## 🎮 Pokemon Identifier API

Identifica Pokémon en imágenes usando **Gemini 2.5 Flash**.

Funciona con juguetes, figuras, cartas, capturas de pantalla, fanart
y cualquier imagen del mundo real. Tier gratuito: 1,500 req/día.
        """,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Process-Time"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        start = time.perf_counter()
        response: Response = await call_next(request)
        response.headers["X-Process-Time"] = (
            f"{(time.perf_counter() - start) * 1000:.2f}ms"
        )
        return response

    register_exception_handlers(app)
    app.include_router(identify_router)

    return app


app = create_app()
