"""
app/core/config.py
Configuracion central de la aplicacion usando variables de entorno.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # API
    APP_NAME: str = "Pokemon Identifier API"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    PORT: int = int(os.getenv("PORT", 8000))

    # Google Gemini 2.5 Flash
    # Clave gratuita en: https://aistudio.google.com -> Get API Key
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    # CORS - URL exacta del frontend con https://, sin barra final
    ALLOWED_ORIGINS: list[str] = [
        origin.strip()
        for origin in os.getenv(
            "ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173"
        ).split(",")
    ]

    # Validacion de imagenes
    MAX_IMAGE_SIZE_BYTES: int = int(os.getenv("MAX_IMAGE_SIZE_MB", 5)) * 1024 * 1024
    ALLOWED_CONTENT_TYPES: set[str] = {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
    }

    # PokeAPI
    POKEAPI_BASE_URL: str = "https://pokeapi.co/api/v2"
    POKEAPI_TIMEOUT: int = 10

    # Confianza minima - resultados por debajo de este % devuelven 404
    MIN_CONFIDENCE_THRESHOLD: float = float(os.getenv("MIN_CONFIDENCE_THRESHOLD", 20))


settings = Settings()
