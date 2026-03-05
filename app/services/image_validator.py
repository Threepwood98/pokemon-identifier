"""
app/services/image_validator.py
Valida que el archivo subido sea una imagen real y dentro de los límites.
"""

import io
from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

from app.core.config import settings
from app.core.exceptions import InvalidImageException, ImageTooLargeException


async def validate_and_read_image(file: UploadFile) -> bytes:
    """
    Lee y valida el archivo de imagen subido.

    Pasos:
    1. Verifica content-type declarado
    2. Verifica tamaño máximo
    3. Verifica que PIL pueda abrirlo (prueba real de integridad)

    Returns:
        bytes: Contenido binario de la imagen validada.

    Raises:
        InvalidImageException: Si el archivo no es una imagen válida.
        ImageTooLargeException: Si supera el tamaño máximo.
    """
    # 1. Verificar content-type
    content_type = file.content_type or ""
    if content_type not in settings.ALLOWED_CONTENT_TYPES:
        raise InvalidImageException(
            f"Tipo de archivo no permitido: '{content_type}'. "
            f"Se aceptan: {', '.join(settings.ALLOWED_CONTENT_TYPES)}"
        )

    # 2. Leer el contenido
    image_bytes = await file.read()

    # 3. Verificar tamaño
    if len(image_bytes) > settings.MAX_IMAGE_SIZE_BYTES:
        max_mb = settings.MAX_IMAGE_SIZE_BYTES // (1024 * 1024)
        raise ImageTooLargeException(max_mb)

    # 4. Verificar que PIL pueda abrirlo (valida la integridad real del archivo)
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.verify()  # Detecta archivos corruptos o truncados
    except (UnidentifiedImageError, Exception):
        raise InvalidImageException(
            "El archivo está corrupto o no es una imagen válida."
        )

    return image_bytes
