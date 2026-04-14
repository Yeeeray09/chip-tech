# CHIP — Documentación del proyecto

---

## La idea

Vi una cuenta de Instagram (@tecnology) que subía 5 o 6 posts al día, siempre a la misma hora, con el mismo formato. Pensé: esto no lo hace una persona. Me puse a investigar y me quedó claro que era automático. Así que decidí hacer lo mismo pero en español y desde cero: @chipitech, una cuenta de noticias tech e IA que se publica sola.

---

## Qué es CHIP

Es un script de Python que hace todo el trabajo: busca noticias, le pide a una IA que genere el contenido, dibuja las imágenes y las sube a Instagram. Tres veces al día, sin que yo haga nada. El nombre CHIP viene de la mascota del proyecto, un robotito que aparece en cada carrusel.

---

## El papel de la IA

La IA aparece en dos sitios.

**En la app:** Claude es el que escribe el contenido de cada carrusel. Le paso el titular y el resumen de la noticia, y él me devuelve los textos de los slides, el caption y decide si la noticia es emocionante, polémica o confusa (eso cambia la expresión de la mascota).

**En el desarrollo:** todo el proyecto lo hice con ayuda de Claude Code y Claude chat. No sabía cómo estructurar el proyecto, no había tocado la API de Meta en mi vida, y el diseño visual lo fuimos ajustando juntos. Pero hay cosas que la IA no puede hacer por ti: crear la cuenta Business de Instagram, configurar la app en Meta for Developers, meter los secrets en GitHub. Esas partes las tuve que entender y hacer yo.

No me da vergüenza decir que usé IA para desarrollar. Lo que aprendí es que tampoco te lo hace todo solo — tienes que entender qué está pasando.

---

## Stack y decisiones técnicas

**Python** porque es lo que sé y tiene librerías para todo esto.

**Pillow** para dibujar las imágenes. Barajé hacer los slides con HTML y capturar pantalla (con Playwright), pero era matar moscas a cañonazos. Con Pillow pinto los fondos, escribo el texto y coloco la mascota directamente, sin navegador.

**Anthropic API** (Claude) para generar el contenido. Podría haber usado ChatGPT, pero llevo tiempo usando Claude y me fío más de cómo escribe en español.

**Meta Graph API** para publicar en Instagram. Es la única forma oficial. Tiene bastante lío con permisos y tokens, pero es lo que hay.

**Cloudinary** porque Meta pide URLs públicas para las imágenes, no puedo pasarle rutas de mi máquina. Subo las imágenes a Cloudinary primero y le paso el enlace a Meta. El plan gratuito me sobra.

**SQLite** para no publicar la misma noticia dos veces. Guardo un hash de cada URL que ya he procesado. Si ya está en la base de datos, la salto.

**GitHub Actions** para ejecutarlo tres veces al día sin pagar hosting. Un YAML con tres líneas de cron y listo.

---

## Cómo funciona (arquitectura)

Cada vez que se ejecuta, el programa hace esto en orden:

1. **`main.py`** arranca todo. También tiene un modo `--test` que genera las imágenes pero no publica, para probar sin gastar llamadas a la API.

2. **`fetcher.py`** lee 20 feeds RSS (The Verge, TechCrunch, Xataka, blogs de OpenAI, Anthropic, etc.), filtra los artículos que hablen de IA o tech y descarta los que ya procesé mirando SQLite.

3. **`generator.py`** manda cada artículo a Claude con un prompt que le dice exactamente qué JSON tiene que devolver: entre 2 y 4 slides según lo compleja que sea la noticia, el caption con hashtags y el "mood" de la noticia.

4. **`renderer.py`** convierte ese JSON en imágenes PNG de 1080x1080. El primer slide (hook) y el último (CTA) son oscuros. Los del medio son claros. Las palabras clave van en verde o azul.

5. **`publisher.py`** sube las imágenes a Cloudinary, coge las URLs y llama a la API de Meta para publicar el carrusel.

SQLite también lleva la cuenta de cuántos carruseles se han publicado, para ir rotando el color del hook entre publicaciones.

---

## El problema del hosting

Necesitaba algo que ejecutara el script tres veces al día y que fuera gratis.

Primero probé **Railway**. Pedía tarjeta de crédito y plan de pago. Descartado.

Luego **Oracle Cloud Free Tier**. Funciona, pero montar un servidor Linux para ejecutar un script de 10 segundos tres veces al día es demasiado. Además tuve varios errores al configurarlo que no sabía resolver.

Al final: **GitHub Actions**. Tiene cron nativo, corre en Ubuntu, instala Python, ejecuta el script y ya. Los secrets de las APIs van en la configuración del repositorio. Gratis, sin complicaciones y puedo ver el log de cada ejecución.

---

## Diseño visual

Todos los carruseles tienen la misma estructura:

- **Slide 1 (hook):** fondo oscuro verde casi negro, texto grande en blanco, grid de puntos, mascota CHIP con la expresión que eligió Claude.
- **Slides del medio:** fondo claro, barra de gradiente arriba, título y texto. Las palabras técnicas importantes van resaltadas en verde o azul.
- **Último slide (CTA):** fondo oscuro igual que el primero, mensaje pidiendo que sigan la cuenta, logo de CHIP.

La mascota tiene cinco expresiones: normal, contenta, emocionada, enfadada y confundida. Claude decide cuál usar según el tono de la noticia.

---

## Estructura del proyecto

```
chip-tech/
├── main.py                  # Arranca todo y coordina los módulos
├── fetcher.py               # Lee RSS y filtra noticias nuevas
├── generator.py             # Llama a Claude y genera el contenido
├── renderer.py              # Dibuja las imágenes con Pillow
├── publisher.py             # Sube a Cloudinary y publica en Instagram
├── requirements.txt         # Dependencias
├── .env.example             # Variables de entorno que hacen falta
├── chip.db                  # SQLite: artículos vistos y contador
├── chip.log                 # Log de cada ejecución
├── assets/
│   ├── fonts/               # Poppins Regular, Bold, SemiBold
│   ├── chip-normal.png      # Mascota neutral
│   ├── chip-happy.png       # Mascota contenta
│   ├── chip-excited.png     # Mascota emocionada
│   ├── chip-angry.png       # Mascota enfadada
│   └── chip.confused-*.png  # Mascota confundida
├── output/                  # Aquí se guardan los PNGs en modo --test
└── .github/
    └── workflows/
        └── publish.yml      # Cron de GitHub Actions (3 veces al día)
```

---

## Tiempo y contexto

Unas 2-3 semanas, pero a ratos. Había días que no tocaba nada y días que le metía muchas horas. Lo hice en paralelo con DAW y con el trabajo. Lo que más tiempo me llevó no fue el código sino entender la API de Meta, que tiene bastante lío con permisos, tipos de token y requisitos de cuenta.

---

## Lo que aprendí

- La API de Instagram no es tan sencilla como parece. Necesitas cuenta Business, una app aprobada en Meta, tokens que caducan y las imágenes tienen que estar en una URL pública. Tardé bastante en hacer que todo encajara.
- GitHub Actions no es solo para tests y deploys. Para automatizar scripts pequeños es perfecto.
- Cuando le pides a una IA que devuelva JSON, tienes que validarlo. A veces mete markdown alrededor, a veces falta un campo. Hay que anticiparlo.
- Usar IA para programar es útil, pero no significa que entiendas menos. Me obligó a entender cada parte porque si no, no podía ni explicarle el problema.
- Para guardar "esto ya lo he visto" en una base de datos, SQLite es más que suficiente.
