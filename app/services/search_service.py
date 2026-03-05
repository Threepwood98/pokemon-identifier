"""
app/services/search_service.py
Realiza la búsqueda inversa de imágenes usando SerpAPI (Google Lens).

SerpAPI actúa como intermediario para evitar bloqueos de CAPTCHA.
Documentación: https://serpapi.com/google-lens-api
"""

import base64
import httpx
from collections import Counter
import re

from app.core.config import settings
from app.core.exceptions import SearchFailedException, MissingAPIKeyException


# Palabras vacías a ignorar en el análisis de frecuencia
STOP_WORDS: set[str] = {
    "the",
    "a",
    "an",
    "in",
    "on",
    "at",
    "to",
    "for",
    "of",
    "and",
    "or",
    "is",
    "it",
    "this",
    "that",
    "with",
    "from",
    "by",
    "as",
    "are",
    "was",
    "be",
    "has",
    "have",
    "had",
    "not",
    "but",
    "so",
    "if",
    "its",
    "la",
    "el",
    "de",
    "en",
    "un",
    "una",
    "los",
    "las",
    "del",
    "al",
    "se",
    "no",
    "image",
    "images",
    "photo",
    "picture",
    "png",
    "jpg",
    "jpeg",
    "gif",
    "pokemon",
    "pokémon",  # excluimos "pokemon" genérico para buscar el nombre específico
    "type",
    "wiki",
    "fandom",
    "bulbapedia",
    "serebii",
    "official",
    "sprite",
    "game",
    "games",
    "nintendo",
    "gamefreak",
    "generation",
    "gen",
}


async def perform_reverse_image_search(image_bytes: bytes) -> list[str]:
    """
    Envía la imagen a SerpAPI (Google Lens) y extrae texto relevante
    de los resultados (títulos, etiquetas, descripciones).

    Returns:
        list[str]: Lista de palabras/tokens extraídos de los resultados.

    Raises:
        MissingAPIKeyException: Si no hay clave de SerpAPI configurada.
        SearchFailedException: Si la búsqueda falla.
    """
    if not settings.SERPAPI_KEY:
        raise MissingAPIKeyException()

    # SerpAPI acepta imágenes como base64 data URI o como URL pública.
    # Usamos base64 para no depender de hosting externo.
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_uri = f"data:image/jpeg;base64,{image_b64}"

    params = {
        "engine": "google_lens",
        "url": data_uri,
        "api_key": settings.SERPAPI_KEY,
        "hl": "en",  # resultados en inglés para mejor coincidencia con PokéAPI
        "no_cache": "true",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                "https://serpapi.com/search",
                params=params,
            )
            response.raise_for_status()
            data = response.json()
    except httpx.TimeoutException:
        raise SearchFailedException("La búsqueda inversa excedió el tiempo de espera.")
    except httpx.HTTPStatusError as e:
        raise SearchFailedException(
            f"Error en SerpAPI (HTTP {e.response.status_code}): {e.response.text[:200]}"
        )
    except Exception as e:
        raise SearchFailedException(f"Error inesperado en la búsqueda: {str(e)}")

    return _extract_tokens_from_results(data)


def _extract_tokens_from_results(data: dict) -> list[str]:
    """
    Extrae y limpia tokens de texto de la respuesta de SerpAPI/Google Lens.

    Fuentes de texto analizadas:
    - visual_matches: título, snippet, fuente
    - knowledge_graph: nombre, descripción
    - text_results: contenido textual encontrado en la imagen
    - related_searches: consultas sugeridas
    """
    raw_texts: list[str] = []

    # 1. Visual matches (resultados de imágenes similares)
    for match in data.get("visual_matches", []):
        if title := match.get("title"):
            raw_texts.append(title)
        if snippet := match.get("snippet"):
            raw_texts.append(snippet)
        if source := match.get("source"):
            raw_texts.append(source)

    # 2. Knowledge graph (panel de conocimiento de Google)
    if kg := data.get("knowledge_graph"):
        if name := kg.get("title"):
            # Los nombres del knowledge graph tienen alta relevancia: los añadimos 3 veces
            raw_texts.extend([name] * 3)
        if desc := kg.get("description"):
            raw_texts.append(desc)

    # 3. Texto detectado dentro de la propia imagen
    for text_result in data.get("text_results", []):
        if text := text_result.get("text"):
            raw_texts.append(text)

    # 4. Búsquedas relacionadas
    for related in data.get("related_searches", []):
        if query := related.get("query"):
            raw_texts.append(query)

    # Tokenizar y limpiar
    tokens: list[str] = []
    for text in raw_texts:
        # Extraer solo palabras alfanuméricas (soporte para guiones tipo "mr-mime")
        words = re.findall(r"[a-zA-Z][a-zA-Z0-9\-]*", text.lower())
        tokens.extend(words)

    return tokens


def compute_word_frequencies(tokens: list[str]) -> Counter:
    """
    Filtra stop words y calcula la frecuencia de cada token.

    Returns:
        Counter ordenado por frecuencia descendente.
    """
    filtered = [
        token for token in tokens if token not in STOP_WORDS and len(token) >= 3
    ]
    return Counter(filtered)
