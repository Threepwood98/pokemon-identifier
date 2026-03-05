"""
app/services/pokemon_matcher.py
Carga la lista de todos los Pokémon desde PokéAPI y cruza los tokens
de búsqueda contra esa lista usando coincidencia exacta y fuzzy matching.
"""

import asyncio
import httpx
from collections import Counter
from cachetools import TTLCache
from thefuzz import fuzz

from app.core.config import settings
from app.core.exceptions import SearchFailedException


# Cache en memoria: guarda la lista de Pokémon por 24 horas
# Evita llamar a PokéAPI en cada request
_pokemon_cache: TTLCache = TTLCache(maxsize=1, ttl=86400)
_cache_lock = asyncio.Lock()


async def get_all_pokemon_names() -> list[str]:
    """
    Obtiene la lista completa de nombres de Pokémon desde PokéAPI.
    El resultado se cachea en memoria por 24 horas.

    Returns:
        list[str]: Lista de nombres en minúsculas (ej. ["bulbasaur", "ivysaur", ...])
    """
    async with _cache_lock:
        if "names" in _pokemon_cache:
            return _pokemon_cache["names"]

        try:
            async with httpx.AsyncClient(timeout=settings.POKEAPI_TIMEOUT) as client:
                # PokéAPI devuelve hasta 100000 Pokémon con limit alto
                response = await client.get(
                    f"{settings.POKEAPI_BASE_URL}/pokemon",
                    params={"limit": 10000, "offset": 0},
                )
                response.raise_for_status()
                data = response.json()
        except Exception as e:
            raise SearchFailedException(
                f"No se pudo obtener la lista de Pokémon de PokéAPI: {str(e)}"
            )

        names = [entry["name"].lower() for entry in data.get("results", [])]
        _pokemon_cache["names"] = names
        return names


def find_best_pokemon_match(
    word_frequencies: Counter,
    all_pokemon_names: list[str],
) -> tuple[str | None, float, list[str]]:
    """
    Cruza las palabras más frecuentes de la búsqueda con la lista de Pokémon.

    Estrategia en dos fases:
    1. Coincidencia EXACTA: el token es exactamente un nombre de Pokémon.
    2. Fuzzy matching: similitud >= FUZZY_MATCH_THRESHOLD (por defecto 85%).

    El "score de confianza" se calcula como:
        (frecuencia del token / total de tokens) * 100

    Returns:
        tuple: (nombre_pokemon | None, confianza_porcentaje, keywords_coincidentes)
    """
    pokemon_set = set(all_pokemon_names)
    total_tokens = sum(word_frequencies.values())

    if total_tokens == 0:
        return None, 0.0, []

    matched_keywords: list[str] = []
    best_match: str | None = None
    best_score: float = 0.0

    # Iteramos por frecuencia descendente (las más repetidas primero)
    for token, count in word_frequencies.most_common(50):

        # Fase 1: coincidencia exacta
        if token in pokemon_set:
            confidence = (count / total_tokens) * 100
            matched_keywords.append(token)
            if confidence > best_score:
                best_score = confidence
                best_match = token
            continue

        # Fase 2: fuzzy matching para manejar errores ortográficos
        # y nombres compuestos (ej. "mr. mime" → "mr-mime")
        cleaned_token = token.replace(" ", "-").replace(".", "")
        for pokemon_name in all_pokemon_names:
            similarity = fuzz.ratio(cleaned_token, pokemon_name)
            if similarity >= settings.FUZZY_MATCH_THRESHOLD:
                confidence = (count / total_tokens) * (similarity / 100) * 100
                matched_keywords.append(token)
                if confidence > best_score:
                    best_score = confidence
                    best_match = pokemon_name
                break

    return best_match, round(best_score, 2), matched_keywords
