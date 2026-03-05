"""
app/core/exceptions.py
Excepciones personalizadas y handlers globales de errores.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class PokemonAPIException(Exception):
    """Excepción base del dominio."""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class InvalidImageException(PokemonAPIException):
    def __init__(
        self, detail: str = "El archivo proporcionado no es una imagen válida."
    ):
        super().__init__(message=detail, status_code=422)


class ImageTooLargeException(PokemonAPIException):
    def __init__(self, max_mb: int = 5):
        super().__init__(
            message=f"La imagen supera el tamaño máximo permitido de {max_mb} MB.",
            status_code=413,
        )


class SearchFailedException(PokemonAPIException):
    def __init__(self, detail: str = "La búsqueda inversa de imágenes falló."):
        super().__init__(message=detail, status_code=503)


class PokemonNotFoundException(PokemonAPIException):
    def __init__(self):
        super().__init__(
            message="No se identificó ningún Pokémon en la imagen proporcionada.",
            status_code=404,
        )


class MissingAPIKeyException(PokemonAPIException):
    def __init__(self):
        super().__init__(
            message="Configuración del servidor incompleta: falta la clave de SerpAPI.",
            status_code=500,
        )


def register_exception_handlers(app: FastAPI) -> None:
    """Registra los handlers globales de excepciones en la app FastAPI."""

    @app.exception_handler(PokemonAPIException)
    async def pokemon_api_exception_handler(
        request: Request, exc: PokemonAPIException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": exc.message,
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "Error interno del servidor. Inténtalo de nuevo más tarde.",
            },
        )
