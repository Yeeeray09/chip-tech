# CHIP — Documentación del proyecto

---

## La idea

Vi una cuenta de Instagram (@tecnology) que publicaba 4-6 posts diarios de noticias tech con un timing demasiado perfecto para ser manual. Intuí que estaba automatizado. Me propuse hacer mi propia versión: @chipitech (CHIP), una cuenta que publica carruseles de noticias tech e IA en español de forma completamente automática, sin que yo tenga que tocar nada.

---

## Qué es CHIP

CHIP es un pipeline de Python que, tres veces al día, busca noticias relevantes por RSS, se las pasa a Claude para que genere el contenido de un carrusel, renderiza las imágenes con Pillow y las publica en Instagram. Sin intervención humana. El resultado es una cuenta activa con contenido real, curado por IA y publicado de forma autónoma.

---

## El papel de la IA

La IA fue central en dos niveles distintos.

**En producción:** Claude (`claude-sonnet-4-5`) es quien genera el contenido de cada carrusel — titulares, textos de slides, caption con hashtags y el "mood" de la noticia. No es un relleno; es la pieza que convierte una noticia en inglés en contenido visual en español con criterio editorial.

**En desarrollo:** todo el proyecto se construyó en colaboración con Claude Code y Claude chat. La arquitectura, la resolución de bugs, el diseño visual, la configuración de APIs, la estructura de módulos — todo fue una conversación continua. Eso no significa que la IA lo hiciera sola: cada credencial, cada cuenta Business de Meta, cada secreto de GitHub Actions requirió que yo tomara decisiones y configurara cosas que ninguna IA puede hacer por ti. Saber usar IA como herramienta de desarrollo es una habilidad en sí misma, y este proyecto me obligó a desarrollarla de verdad.

---

## Stack y decisiones técnicas

El proyecto usa **Python** como lenguaje principal — ecosistema maduro para este tipo de pipelines, sin necesidad de justificación. Para el renderizado de imágenes elegí **Pillow** en lugar de soluciones basadas en navegador (Playwright/Puppeteer) o servicios externos: Pillow es control total, sin dependencias pesadas, y para slides 1080x1080 es más que suficiente.

El contenido lo genera **Claude via la Anthropic API** (`claude-sonnet-4-5`). La alternativa era GPT-4, pero trabajo con Claude habitualmente y la calidad en español es sólida. Para la publicación uso la **Meta Graph API v19.0** directamente con `requests` — es la única vía oficial para publicar carruseles en Instagram desde código.

El problema que no anticipé: Meta Graph API exige URLs públicas para las imágenes, no rutas locales. Por eso añadí **Cloudinary** — subo las imágenes ahí primero y paso las URLs a Meta. Es un paso extra, pero el plan gratuito de Cloudinary cubre perfectamente el volumen del proyecto.

Para evitar publicar la misma noticia dos veces uso **SQLite** con una tabla `seen_articles`. No necesitaba nada más complejo. El `uid` de cada artículo es un hash SHA-256 de su URL, así que es determinista y barato de calcular.

---

## Cómo funciona (arquitectura)

El pipeline sigue este orden cada vez que se ejecuta:

1. **`main.py`** — orquesta todo. Parsea argumentos (`--test` para generar sin publicar), llama a cada módulo en secuencia y gestiona errores por artículo para que un fallo no corte el resto de la ejecución.

2. **`fetcher.py`** — consulta 20 fuentes RSS (The Verge, TechCrunch, Wired, Xataka, blogs de OpenAI, Anthropic, Google AI, etc.), filtra por keywords de IA y tech, y descarta artículos ya vistos consultando SQLite. Devuelve los artículos nuevos y relevantes.

3. **`generator.py`** — toma cada artículo y lo envía a Claude con un prompt estructurado. Claude devuelve JSON con el contenido de los slides (2-4 según la complejidad de la noticia), el caption y el "mood" (`excited`, `angry`, `confused`, `happy`). El módulo valida el JSON y añade un slide CTA fijo al final.

4. **`renderer.py`** — convierte el contenido en imágenes PNG 1080x1080 con Pillow. Slide 1 (hook) y el CTA son oscuros con fondo degradado verde oscuro. Los slides intermedios son claros con gradiente en la barra superior. Las keywords marcadas con `**doble asterisco**` se renderizan en verde o azul según la paleta.

5. **`publisher.py`** — sube las imágenes a Cloudinary, obtiene las URLs públicas y llama a la Meta Graph API para crear y publicar el carrusel en Instagram.

SQLite también lleva un contador de publicaciones para rotar el color del hook (blanco / verde / azul) entre carruseles consecutivos.

---

## El problema del hosting

Necesitaba ejecutar el pipeline tres veces al día de forma fiable y gratuita.

Probé **Railway** primero — requería tarjeta de crédito y pasarse al plan de pago para algo tan simple. Lo descarté. Intenté con **Oracle Cloud Free Tier** — el servidor funciona, pero la configuración fue innecesariamente compleja para un script que se ejecuta unos segundos tres veces al día.

La solución fue **GitHub Actions**. Un YAML con tres crons (`0 8`, `0 13`, `0 18` UTC), `ubuntu-latest`, Python 3.11, `pip install -r requirements.txt` y `python main.py`. Los secrets (claves de API) van en el repositorio como GitHub Secrets. Gratuito, simple, auditable, con logs por ejecución. En retrospectiva era la respuesta obvia desde el principio.

---

## Diseño visual

El sistema de slides sigue una estructura fija de tres tipos:

- **Hook (slide 1):** fondo oscuro (`#0a1a0f` → `#0d2818`), tipografía grande en blanco, grid de puntos tech superpuesto, mascota CHIP en la esquina con la expresión del mood de la noticia.
- **Slides de contenido (intermedios):** fondo claro (`#F7FAF8`), barra de gradiente verde en la parte superior, título en oscuro, texto en gris, keywords técnicas resaltadas en verde (`#00D96F`) o azul (`#0099FF`).
- **CTA (último slide):** mismo estilo oscuro que el hook, mensaje de seguimiento rotando entre tres variantes, logo de CHIP.

La mascota CHIP tiene cinco expresiones — `normal`, `happy`, `excited`, `angry`, `confused` — que Claude elige según el tono de la noticia. Es un detalle pequeño pero da personalidad a la cuenta.

---

## Estructura del proyecto

```
chip-tech/
├── main.py                  # Orquestador principal
├── fetcher.py               # Lector de RSS + deduplicación con SQLite
├── generator.py             # Generación de contenido con Claude
├── renderer.py              # Renderizado de imágenes con Pillow
├── publisher.py             # Subida a Cloudinary + publicación en Instagram
├── requirements.txt         # Dependencias Python
├── .env.example             # Variables de entorno necesarias (sin valores)
├── chip.db                  # Base de datos SQLite (artículos vistos + contador)
├── chip.log                 # Log de ejecuciones
├── assets/
│   ├── fonts/               # Poppins Regular, Bold, SemiBold
│   ├── chip-normal.png      # Mascota — expresión neutral
│   ├── chip-happy.png       # Mascota — alegre
│   ├── chip-excited.png     # Mascota — emocionado
│   ├── chip-angry.png       # Mascota — enfadado
│   └── chip.confused-*.png  # Mascota — confundido
├── output/                  # PNGs generados en modo --test
└── .github/
    └── workflows/
        └── publish.yml      # GitHub Actions: 3 ejecuciones diarias
```

---

## Tiempo y contexto

Unas 2-3 semanas de trabajo irregular, en paralelo con DAW y trabajo. No fue un sprint continuo — hubo días de nada y días de muchas horas. La mayor parte del tiempo no fue escribir código sino entender cómo funcionan las APIs de Meta (que tienen su propia lógica), configurar cuentas Business, y depurar problemas de credenciales y permisos.

---

## Lo que aprendí

- La Meta Graph API para Instagram tiene más requisitos de los que parece: cuenta Business, app revisada, tokens de larga duración, y las imágenes deben ser URLs públicas, no locales. Cloudinary resolvió esto último.
- GitHub Actions es una plataforma de automatización, no solo de CI/CD. Para scripts programados y simples es imbatible.
- Diseñar un prompt para que Claude devuelva JSON válido y estructurado de forma consistente requiere iterar. El parsing defensivo (limpiar markdown fences, validar campos, defaults) es necesario.
- Usar IA para desarrollar no significa delegar. Significa colaborar — la IA propone, tú decides, y hay partes que simplemente no puede hacer por ti.
- SQLite para deduplicación simple es la herramienta correcta. No todo necesita una base de datos real.
