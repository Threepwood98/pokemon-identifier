"""
app/services/pokeapi_service.py
Obtiene los detalles completos de un Pokémon desde PokéAPI.
"""

import httpx
from app.core.config import settings
from app.models.schemas import PokemonDetails, PokemonType, PokemonStats


async def fetch_pokemon_details(pokemon_name: str) -> PokemonDetails | None:
    """
    Consulta PokéAPI para obtener los datos básicos del Pokémon identificado.

    Returns:
        PokemonDetails | None: Datos del Pokémon, o None si no se puede obtener.
    """
    url = f"{settings.POKEAPI_BASE_URL}/pokemon/{pokemon_name.lower()}"

    try:
        async with httpx.AsyncClient(timeout=settings.POKEAPI_TIMEOUT) as client:
            response = await client.get(url)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            data = response.json()
    except Exception:
        # Los detalles son opcionales: si fallan, no rompemos la respuesta
        return None

    # Extraer tipos
    types = [
        PokemonType(
            slot=t["slot"],
            name=t["type"]["name"],
        )
        for t in data.get("types", [])
    ]

    # Extraer stats por nombre
    stats_map: dict[str, int] = {
        s["stat"]["name"]: s["base_stat"]
        for s in data.get("stats", [])
    }

    stats = PokemonStats(
        hp=stats_map.get("hp", 0),
        attack=stats_map.get("attack", 0),
        defense=stats_map.get("defense", 0),
        speed=stats_map.get("speed", 0),
    )

    # Sprite oficial
    sprites = data.get("sprites", {})
    sprite_url = (
        sprites.get("other", {}).get("official-artwork", {}).get("front_default")
        or sprites.get("front_default")
    )

    return PokemonDetails(
        id=data["id"],
        name=data["name"],
        height=data["height"] / 10,   # PokéAPI usa decímetros → metros
        weight=data["weight"] / 10,   # PokéAPI usa hectogramos → kilogramos
        types=types,
        stats=stats,
        sprite_url=sprite_url,
        pokeapi_url=url,
    )