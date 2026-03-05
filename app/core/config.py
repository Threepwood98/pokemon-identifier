"""
app/core/config.py
Configuración central de la aplicación usando variables de entorno.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # API
    APP_NAME: str = "Pokemon Identifier API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    PORT: int = int(os.getenv("PORT", 8000))

    # Google Gemini Flash (fallback gratuito cuando ViT < 80%)
    # Obtén tu clave gratis en: https://aistudio.google.com
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    # SerpAPI — mantenido por compatibilidad pero ya no se usa activamente
    SERPAPI_KEY: str = os.getenv("SERPAPI_KEY", "")

    # CORS
    ALLOWED_ORIGINS: list[str] = [
        origin.strip()
        for origin in os.getenv(
            "ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173"
        ).split(",")
    ]

    # Validación de imágenes
    MAX_IMAGE_SIZE_BYTES: int = int(os.getenv("MAX_IMAGE_SIZE_MB", 5)) * 1024 * 1024
    ALLOWED_CONTENT_TYPES: set[str] = {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
    }

    # PokéAPI
    POKEAPI_BASE_URL: str = "https://pokeapi.co/api/v2"
    POKEAPI_TIMEOUT: int = 10

    # Umbrales de confianza
    MIN_CONFIDENCE_THRESHOLD: float = 20.0  # % mínimo para retornar un resultado
    FUZZY_MATCH_THRESHOLD: int = 85  # similitud mínima (0-100) para fuzzy matching

    # Modelo ViT
    VIT_MODEL_ID: str = "imzynoxprince/pokemons-image-classifier-gen1-gen9"
    VIT_ENABLED: bool = True
    VIT_CONFIDENCE_THRESHOLD: float = 80.0
    VIT_FALLBACK_THRESHOLD: float = 40.0  # % por debajo del cual se activa SerpAPI


settings = Settings()
