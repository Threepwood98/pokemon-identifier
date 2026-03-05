# 🎮 Pokemon Identifier API

API RESTful que identifica un Pokémon a partir de una imagen usando un sistema híbrido de dos etapas: un modelo **ViT local** (Vision Transformer) como clasificador principal y **Gemini 2.5 Flash** de Google como fallback inteligente para imágenes del mundo real.

---

## ⚙️ Cómo funciona

```
              [ Cliente / App Web ]
                        │
                        ▼
            [ API Gateway (FastAPI) ]
                        │
                        ▼
              [ Modelo ViT (Local) ] ◄─────┐
                        │                  │
                ¿Confianza >= 80%?         │
                 /              \          │
              (SÍ)              (NO)       │
               │                 │         │
               ▼                 ▼         │
        [ VIT_DIRECT ]    [ Gemini Flash ] │
               │                 │         │
               │          ¿Gemini falló? ──┘
               │                 │
               ▼                 ▼
            [ Enriquecimiento PokéAPI ]
                        │
                        ▼
                [ Respuesta JSON ]
```

---

## 📁 Estructura del Proyecto

```
pokemon-identifier/
│
├── app/
│   ├── api/
│   │   └── routes/
│   │       └── identify.py          # ← CONTROLADOR PRINCIPAL
│   │
│   ├── core/
│   │   ├── config.py                # Variables de entorno y settings
│   │   └── exceptions.py           # Excepciones personalizadas y handlers
│   │
│   ├── models/
│   │   └── schemas.py               # Modelos Pydantic (request/response)
│   │
│   ├── services/
│   │   ├── image_validator.py       # Validación de archivos de imagen
│   │   ├── vit_classifier.py        # Modelo ViT con lazy loading + idle unload
│   │   ├── gemini_classifier.py     # Gemini 1.5 Flash (fallback gratuito)
│   │   ├── pokemon_matcher.py       # Cruce con catálogo PokéAPI
│   │   └── pokeapi_service.py       # Detalles desde PokéAPI
│   │
│   └── main.py                      # Factory de la app (CORS, middleware, lifespan)
│
├── main.py                          # Entrypoint del servidor
├── Dockerfile                       # Build optimizado para Railway
├── railway.toml                     # Configuración de Railway
├── requirements.txt
└── .env.example
```

---

## 🚀 Instalación y Configuración Local

### 1. Clonar y crear entorno virtual

```bash
git clone <tu-repo>
cd pokemon-identifier

python -m venv venv
source venv/bin/activate        # Linux/Mac
# venv\Scripts\activate         # Windows
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 3. Configurar variables de entorno

```bash
cp .env.example .env
# Editar .env y añadir tu GEMINI_API_KEY
```

Obtén tu clave **gratuita** en: https://aistudio.google.com → **Get API Key**

### 4. Ejecutar el servidor

```bash
python main.py

# O con uvicorn directamente:
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 🚂 Despliegue en Railway

### Variables de entorno requeridas en Railway → Settings → Variables:

| Variable                   | Requerida | Descripción                                                |
| -------------------------- | --------- | ---------------------------------------------------------- |
| `GEMINI_API_KEY`           | **Sí**    | Clave de Google AI Studio (gratis en aistudio.google.com)  |
| `ALLOWED_ORIGINS`          | **Sí**    | URL exacta de tu frontend con `https://`                   |
| `VIT_CONFIDENCE_THRESHOLD` | No        | Umbral ViT directo en % (default: `80`)                    |
| `MIN_CONFIDENCE_THRESHOLD` | No        | Confianza mínima global en % (default: `10`)               |
| `VIT_IDLE_TIMEOUT`         | No        | Segundos hasta descargar el modelo de RAM (default: `300`) |
| `DEBUG`                    | No        | Modo debug (default: `false`)                              |

### Pasos:

1. Sube el proyecto a GitHub
2. En Railway → **New Project** → **Deploy from GitHub repo**
3. Selecciona el repositorio — Railway detecta el `Dockerfile` automáticamente
4. Añade las variables de entorno
5. Railway hace el build (~5–10 min la primera vez, el modelo ViT se descarga durante el build)

---

## 🔌 Endpoints

### `POST /api/identify-pokemon`

Identifica el Pokémon en la imagen proporcionada.

**Request:** `multipart/form-data`

| Campo  | Tipo | Descripción                               |
| ------ | ---- | ----------------------------------------- |
| `file` | File | Imagen (JPEG, PNG, WEBP, GIF · máx. 5 MB) |

**Response 200:**

```json
{
  "success": true,
  "pokemon_name": "charizard",
  "confidence": 97.4,
  "detection_method": "vit_direct",
  "matched_keywords": [],
  "details": {
    "id": 6,
    "name": "charizard",
    "height": 1.7,
    "weight": 90.5,
    "types": [
      { "slot": 1, "name": "fire" },
      { "slot": 2, "name": "flying" }
    ],
    "stats": {
      "hp": 78,
      "attack": 84,
      "defense": 78,
      "speed": 100
    },
    "sprite_url": "https://raw.githubusercontent.com/.../charizard.png",
    "pokeapi_url": "https://pokeapi.co/api/v2/pokemon/charizard"
  }
}
```

El campo `detection_method` indica qué motor identificó el Pokémon:

| Valor           | Significado                                              |
| --------------- | -------------------------------------------------------- |
| `vit_direct`    | ViT con ≥ 80% de confianza — respuesta directa (~0.2s)   |
| `gemini_vision` | Gemini 2.5 Flash — ViT con baja confianza (~1–2s)        |
| `vit_fallback`  | Gemini falló — se usó el ViT como último recurso (~0.2s) |

**Response 404** (no identificado):

```json
{
  "success": false,
  "error": "No se identificó ningún Pokémon en la imagen proporcionada."
}
```

### `GET /api/health`

Estado del servicio y sus dependencias.

```json
{
  "status": "ok",
  "service": "Pokemon Identifier API (ViT + Gemini Flash)",
  "vit_model_loaded": true,
  "gemini_configured": true,
  "thresholds": {
    "vit_direct": "80%",
    "min_global": "10%"
  }
}
```

### `GET /docs`

Swagger UI interactivo con pruebas en vivo.

---

## 🌐 Uso desde el Frontend (JavaScript)

```javascript
async function identifyPokemon(imageFile) {
  const formData = new FormData();
  formData.append("file", imageFile);

  const response = await fetch(
    "https://tu-api.up.railway.app/api/identify-pokemon",
    {
      method: "POST",
      body: formData,
      // No añadir Content-Type manualmente — el navegador lo hace automáticamente
    },
  );

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.error || "Error desconocido");
  }

  return data;
}

// Ejemplo de uso en un input de archivo:
document
  .getElementById("pokemon-image")
  .addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    try {
      const result = await identifyPokemon(file);
      console.log(
        `Pokémon: ${result.pokemon_name} (${result.confidence}% confianza)`,
      );
      console.log(`Motor: ${result.detection_method}`);
      console.log(`Sprite: ${result.details?.sprite_url}`);
    } catch (error) {
      console.error("Error:", error.message);
    }
  });
```

---

## 🧠 Lógica del Modelo ViT

El modelo ViT corre **localmente en Railway** (sin coste por inferencia):

- Se descarga una vez durante el `docker build` (~350 MB, Hugging Face)
- Se carga en RAM cuando llega la primera request (**lazy loading**)
- Se descarga automáticamente de RAM tras **5 minutos sin uso** para liberar memoria
- Corre en **CPU** — sin necesidad de GPU

Para el tier de Railway Hobby, el coste de RAM del modelo cargado ~6h/día es de aproximadamente **$1.40/mes**, bien dentro de los $5 de créditos incluidos.

---

## 💡 Tipos de Imagen Soportados

| Tipo de imagen                 | Motor usado  | Precisión esperada |
| ------------------------------ | ------------ | ------------------ |
| Sprites oficiales / artwork    | ViT directo  | ★★★★★              |
| Capturas de pantalla del juego | ViT / Gemini | ★★★★★              |
| Cartas Pokémon fotografiadas   | Gemini       | ★★★★☆              |
| Figuras / peluches             | Gemini       | ★★★★☆              |
| Fanart / ilustraciones         | Gemini       | ★★★☆☆              |
| Fotos borrosas o parciales     | Gemini       | ★★☆☆☆              |

---

## 🔧 Variables de Entorno

| Variable                   | Default                         | Descripción                                                 |
| -------------------------- | ------------------------------- | ----------------------------------------------------------- |
| `GEMINI_API_KEY`           | —                               | **Requerida.** Clave de Google AI Studio                    |
| `ALLOWED_ORIGINS`          | `localhost:3000,localhost:5173` | Orígenes CORS (separados por coma, con `https://`)          |
| `MAX_IMAGE_SIZE_MB`        | `5`                             | Tamaño máximo de imagen en MB                               |
| `PORT`                     | `8000`                          | Puerto del servidor (Railway lo asigna automáticamente)     |
| `DEBUG`                    | `false`                         | Modo debug                                                  |
| `VIT_CONFIDENCE_THRESHOLD` | `80`                            | % mínimo para respuesta directa del ViT                     |
| `MIN_CONFIDENCE_THRESHOLD` | `10`                            | % mínimo global — por debajo devuelve 404                   |
| `VIT_IDLE_TIMEOUT`         | `300`                           | Segundos de inactividad antes de descargar el modelo de RAM |

---

## 📦 Dependencias Clave

| Paquete               | Propósito                              |
| --------------------- | -------------------------------------- |
| `fastapi`             | Framework web asíncrono                |
| `uvicorn`             | Servidor ASGI de alto rendimiento      |
| `transformers`        | Pipeline del modelo ViT (Hugging Face) |
| `torch`               | Backend de inferencia del ViT          |
| `google-generativeai` | Cliente de Gemini 2.5 Flash            |
| `httpx`               | Cliente HTTP asíncrono para PokéAPI    |
| `Pillow`              | Validación de integridad de imágenes   |
| `thefuzz`             | Fuzzy matching para nombres de Pokémon |
| `cachetools`          | Cache TTL en memoria para el catálogo  |
| `python-multipart`    | Soporte para subida de archivos        |
