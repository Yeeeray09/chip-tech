"""
generator.py — Uses Claude to generate 6 slides + caption per article.
Keywords in slide text are wrapped with **double asterisks** for highlight rendering.
"""

import json
import logging
import os
import re
from dataclasses import dataclass

import anthropic
from dotenv import load_dotenv

from fetcher import Article, get_hook_color_idx

load_dotenv()
log = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-5"

SYSTEM_PROMPT = """Eres el redactor de CHIP, una cuenta de Instagram sobre tecnología e IA en español.
Tu misión: convertir noticias técnicas en carruseles visuales atractivos para audiencias hispanohablantes.

REGLAS ESTRICTAS:
- Responde SOLO con JSON válido, sin texto adicional, sin bloques de código markdown.
- Todo el contenido (títulos, textos, caption) debe estar en ESPAÑOL.
- Usa **doble asterisco** alrededor de palabras clave técnicas importantes en los textos de los slides.
- El caption debe ser conversacional, incluir emojis y terminar con la fuente.
- Nunca inventes datos que no estén en el artículo.
"""

SLIDE_SCHEMA = """
Decide cuántos slides necesita esta noticia: mínimo 2, máximo 4.
- Noticias simples o breves → 2 slides
- Noticias con contexto moderado → 3 slides
- Noticias complejas o con múltiples ángulos → 4 slides

Devuelve exactamente este JSON (sin markdown, sin explicaciones):
{
  "mood": "<uno de: happy, excited, angry, confused>",
  "slides": [
    {
      "slide_number": 1,
      "title": "Titular gancho MUY impactante, máximo 8 palabras, sin punto final"
    },
    {
      "slide_number": 2,
      "title": "Título corto (<= 6 palabras)",
      "text": "Texto de 2-3 oraciones con **palabras clave** marcadas. Máx 200 caracteres."
    }
    ... (entre 2 y 4 slides en total; solo slide 1 omite el campo "text")
  ],
  "caption": "Caption conversacional en español con emojis. Explica la noticia, por qué importa, y termina con: 📰 Fuente: [nombre de la fuente]\\n\\n#IA #Tech #Tecnología #InteligenciaArtificial #CHIP"
}

Reglas para "mood" (elige UNO):
- excited  → avances tecnológicos, lanzamientos, logros científicos, récords
- angry    → controversias, escándalos, críticas, regulaciones punitivas, despidos masivos
- confused → noticias ambiguas, resultados contradictorios, predicciones inciertas
- happy    → cualquier otra noticia positiva o neutral

Estructura de slides:
- Slide 1 (siempre) = Hook visual: solo título, sin "text"
- Slide 2           = Contexto / qué pasó
- Slide 3 (si n≥3)  = Detalle técnico o dato clave
- Slide 4 (si n=4)  = Conclusión / call to action ("¿Qué opinas? 👇")
"""


VALID_MOODS = {"happy", "excited", "angry", "confused"}

CTA_MESSAGES = [
    "Síguenos para más\nnoticias tech\ncada día",
    "No te pierdas\nlo último en\nIA y tecnología",
    "Únete a la\ncomunidad tech\nde @chipitech",
]


@dataclass
class Slide:
    slide_number: int
    title: str
    text: str = ""
    is_cta: bool = False


@dataclass
class CarouselContent:
    article: Article
    slides: list[Slide]
    caption: str
    mood: str = "happy"
    hook_color_idx: int = 0  # 0=white, 1=green, 2=blue


def _build_user_prompt(article: Article) -> str:
    return f"""Artículo a convertir en carrusel de Instagram:

Fuente: {article.source}
Título: {article.title}
URL: {article.url}
Resumen: {article.summary}

{SLIDE_SCHEMA}"""


def _parse_response(raw: str, article: Article) -> CarouselContent:
    # Strip accidental markdown fences
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)

    data = json.loads(cleaned)

    slides = [
        Slide(
            slide_number=s["slide_number"],
            title=s["title"].strip(),
            text=s.get("text", "").strip(),
        )
        for s in data["slides"]
    ]

    if not (2 <= len(slides) <= 4):
        raise ValueError(f"Expected 2-4 slides, got {len(slides)}")

    raw_mood = str(data.get("mood", "happy")).strip().lower()
    mood = raw_mood if raw_mood in VALID_MOODS else "happy"
    if mood != raw_mood:
        log.warning("Unexpected mood value '%s', defaulting to 'happy'", raw_mood)

    # Append fixed CTA slide as the last slide
    hook_color_idx = get_hook_color_idx()
    cta_number = len(slides) + 1
    cta_text = CTA_MESSAGES[hook_color_idx % len(CTA_MESSAGES)]
    slides.append(Slide(
        slide_number=cta_number,
        title=cta_text,
        is_cta=True,
    ))

    return CarouselContent(
        article=article,
        slides=slides,
        caption=data["caption"].strip(),
        mood=mood,
        hook_color_idx=hook_color_idx,
    )


def generate_carousel(article: Article) -> CarouselContent:
    """Call Claude to generate slide content for a single article."""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    log.info("Generating carousel for: %s", article.title[:60])

    message = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_user_prompt(article)}],
    )

    raw = message.content[0].text
    log.debug("Raw response: %s", raw[:200])

    try:
        carousel = _parse_response(raw, article)
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        log.error("Failed to parse Claude response: %s\nRaw:\n%s", exc, raw)
        raise

    log.info("  Generated %d slides + caption (mood: %s)", len(carousel.slides), carousel.mood)
    return carousel
