# CLAUDE.md - Registro del proyecto comarb-twitter

## Descripcion del proyecto
Herramienta de scraping y analisis de sentimiento de tweets relacionados con organismos de COMARB (Comision Arbitral del Convenio Multilateral). Busca tweets por keywords (`comarb`, `sifere`, `sircar`, `sirpei`, `sircreb`, `sircupa`, `sirtac`), analiza sentimiento y genera reportes HTML interactivos publicados en GitHub Pages.

## Stack tecnico
- **Lenguaje:** Python (async)
- **Scraping:** twikit (API interna de Twitter/X)
- **Analisis:** Sentimiento propio con emojis y puntuacion
- **CI/CD:** GitHub Actions (workflow `update-report.yml`)
- **Output:** `tweets_data.json` + `docs/index.html` (GitHub Pages)
- **Multi-cuenta:** Soporte para distribuir keywords entre multiples cuentas de Twitter

## Archivos clave
- `main.py` — Script principal: login, scraping, analisis de sentimiento, guardado de datos
- `report_generator.py` — Genera el dashboard HTML desde los datos JSON
- `setup_cookies.py` — Configuracion de cookies para autenticacion multi-cuenta
- `.github/workflows/update-report.yml` — Workflow automatico de actualizacion
- `tweets_data.json` — Datos crudos de tweets
- `docs/index.html` — Dashboard interactivo (GitHub Pages)
- `docs/tweets_data.json` — Copia de datos para el frontend

## Registro de sesiones

### Sesion 1 — 2026-03-27
**Consultas realizadas:**
1. Verificacion de sincronizacion entre carpeta local y repo remoto `framirez-comarb/comarb-twitter`
   - Resultado: local estaba 6 commits atras (actualizaciones automaticas del reporte)
   - Accion: se ejecuto `git pull origin main` para sincronizar
2. Eliminacion de tweets duplicados en las busquedas
   - Problema: no existia ningun mecanismo de deduplicacion; tweets podian repetirse dentro de una misma busqueda (paginacion) y entre busquedas de distintos keywords
   - Solucion: se agrego un `set` compartido (`seen_ids`) que se pasa entre todas las busquedas de keywords. Cada tweet se verifica contra este set antes de procesarse
   - Archivos modificados: `main.py`
     - `search_keyword_with_client()` — nuevo parametro `seen_ids`, chequeo de duplicados en el loop de tweets
     - `scrape_tweets()` — creacion del `seen_ids` compartido y pasaje a cada busqueda
   - Commit: `c483af0` — "Deduplicate tweets within and across keyword searches"
3. Mejora del analisis de sentimiento con vocabulario argentino
   - Problema: diccionario muy basico (~58 neg, ~13 pos), sin lunfardo, insultos argentinos, expresiones coloquiales ni intensificadores
   - Solucion:
     - Creado `sentiment_lexicon.py` con 187 palabras negativas, 98 positivas, 73 frases negativas, 40 frases positivas, 9 negaciones, 18 intensificadores, 13 marcadores de sarcasmo
     - Reescrita `analyze_sentiment()` con: matching de frases multi-palabra, negaciones que invierten polaridad (70%), intensificadores argentinos (re, recontra, tremendo, alto), heuristica de sarcasmo
     - Nueva formula ponderada: palabras 0.40 + frases 0.25 + emojis 0.25 + TextBlob 0.10
     - Umbral ajustado a +/-0.10
   - Archivos: `sentiment_lexicon.py` (nuevo), `main.py` (refactorizado analyze_sentiment + helpers)
   - Test: 15/15 casos argentinos correctos

### Sesion 2 — 2026-04-07
**Consultas realizadas:**
1. Fix del workflow de GitHub Actions
   - Problema: el workflow `update-report.yml` fallaba en `pip install -r requirements.txt` con `Could not find a version that satisfies the requirement pysentimiento>=0.7.6`. La ultima version publicada en PyPI es 0.7.3.
   - Solucion: bajar la restriccion a `pysentimiento>=0.7.3` en `requirements.txt`.
   - Commit: `2d15e5e`
2. Bump de actions a versiones con Node.js 24
   - Problema: warning de deprecacion de Node.js 20 en el runner.
   - Solucion: `actions/checkout@v4 → v5`, `actions/setup-python@v5 → v6`, `actions/cache@v4 → v5` en `.github/workflows/update-report.yml`.
   - Commit: `29c78b9`
3. Dashboard: nueva columna "Top con mas likes" en `report_generator.py`
   - Se agrego `top_liked_posts = sorted(all_posts, key=likes)[:N]`.
   - Layout en 2 columnas con `.timeline-grid` (recientes a la izquierda, top likes a la derecha).
   - Pills `.timeline-likes` con icono ❤️ y count.
4. Ajustes de los listados de tweets
   - `-webkit-line-clamp` subido a 5 (eran 2, luego 3) para mostrar mas lineas por tweet.
   - Truncado de texto subido de 180 a 280 chars.
   - Ambos listados mostraban inicialmente 10 tweets, luego subidos a 12. Titulo "Top 10 con mas likes" → "Top 12 con mas likes".
   - Se agrego la fecha del tweet en la columna de Top con mas likes.
5. Nueva seccion "Frases asociadas por palabra clave (top 5)"
   - Pills proporcionales al count, coloreadas por sentimiento dominante (no se uso wordcloud por ser overkill con solo 5 items).
   - Funciones nuevas en `report_generator.py`:
     - `_tokenize()` — limpia urls/menciones/puntuacion, filtra stopwords ES.
     - `_extract_top_ngrams()` — extrae bi/tri/4-gramas, dedupe por substring, prefiere mas largo en empates.
     - `_merge_overlapping()` — combina n-gramas que comparten ≥2 tokens consecutivos (ej: "activa menem scioli" + "menem scioli pareja" → "casta esta activa menem scioli pareja"). Limite `_MAX_MERGED_TOKENS = 6` y rechazo de merges con tokens duplicados.
   - CSS: `.ngram-card`, `.ngram-pill` (variantes positivo/negativo/neutro), tamaño 11px–18px proporcional.
   - Keywords sin frases frecuentes (ej: SIRPEI con solo 4 tweets) no generan tarjeta vacia, se listan junto al titulo: "— sin frases frecuentes: SIRPEI".
6. Mejoras al chart "Distribucion de sentimiento por sistema"
   - Labels del eje Y ahora muestran total entre parentesis: "SIRCREB (41)".
   - Padding extra (`layout.padding.left: 20`, `ticks.padding: 8`, `afterFit` con `scale.width >= 120`) para evitar que se recorten las "S" iniciales.
   - Tooltip:
     - Linea 1 (titulo): keyword sin el "(N)" — strippeado con regex en callback `title`.
     - Linea 2: muestra conteo absoluto + %, ej: "Negativo: 26 tweets (63.4%)". Counts pasados como campo extra `counts` en cada dataset.
- Commit final del dashboard: `b11b593` — "Dashboard: top frases por keyword, top likes y mejoras varias"

## Notas tecnicas
- El workflow de GitHub Actions genera commits automaticos con formato "Reporte actualizado: YYYY-MM-DD HH:MM UTC"
- Las keywords se distribuyen entre cuentas con round-robin: `clients_info[i % n_clients]`
- Hay un monkey-patch para twikit por compatibilidad con regex de `ondemand.s`
- MAX_TWEETS_PER_KEYWORD = 200
- Pausa de 30s entre keywords, 3s entre paginas, 60s en rate limit (429)
