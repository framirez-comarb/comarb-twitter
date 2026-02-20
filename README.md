# 📊 COMARB — Análisis de Sentimiento Twitter/X

Dashboard automático que scrapea tweets sobre los sistemas tributarios de COMARB y publica un reporte interactivo en GitHub Pages, actualizado diariamente.

**Palabras clave:** `comarb` · `sifere` · `sircar` · `sirpei` · `sircreb` · `sircupa` · `sirtac`

---

## 🚀 Setup paso a paso

### Paso 1: Crear el repositorio en GitHub

1. Andá a [github.com/new](https://github.com/new)
2. Nombre: `comarb-sentimiento` (o el que quieras)
3. Visibilidad: **Public** (necesario para GitHub Pages gratis)
4. **NO** marques "Add a README" (vamos a subir los archivos)
5. Clic en **Create repository**

### Paso 2: Subir los archivos

Abrí una terminal y ejecutá:

```bash
# Cloná el repo vacío
git clone https://github.com/TU_USUARIO/comarb-sentimiento.git
cd comarb-sentimiento

# Copiá todos los archivos del proyecto a esta carpeta
# (main.py, report_generator.py, setup_cookies.py, requirements.txt,
#  .gitignore, .github/, docs/)

# Primer push
git add .
git commit -m "🚀 Setup inicial"
git push origin main
```

### Paso 3: Generar las cookies de Twitter

Este es el paso clave. GitHub Actions necesita tus cookies de Twitter para buscar tweets.

```bash
# Ejecutá el asistente de configuración
python setup_cookies.py
```

El script te va a:
1. Pedir tus credenciales de Twitter/X (o cookies del navegador)
2. Generar un texto en base64 con las cookies
3. Mostrarte ese texto para que lo copies

### Paso 4: Configurar el Secret en GitHub

1. Andá a tu repositorio en GitHub
2. **Settings** → **Secrets and variables** → **Actions**
3. Clic en **New repository secret**
4. Name: `TWITTER_COOKIES`
5. Value: pegá el texto base64 que te dio el script
6. Clic en **Add secret**

### Paso 5: Activar GitHub Pages

1. En tu repositorio → **Settings** → **Pages**
2. Source: **Deploy from a branch**
3. Branch: **main** / Folder: **/docs**
4. Clic en **Save**

### Paso 6: Ejecutar el primer reporte

1. Andá a **Actions** en tu repositorio
2. En la barra lateral, clic en **📊 Actualizar Reporte de Sentimiento**
3. Clic en **Run workflow** → **Run workflow**
4. Esperá unos minutos a que termine (podés ver el progreso en el log)

### ¡Listo! 🎉

Tu reporte está disponible en:
```
https://TU_USUARIO.github.io/comarb-sentimiento/
```

---

## 📅 Actualización automática

El GitHub Action se ejecuta **todos los días a las 08:00 AM hora Argentina** (11:00 UTC).

También podés:
- **Ejecutar manualmente** desde la pestaña Actions → Run workflow
- **Actualizar al hacer push** de cambios en `main.py` o `report_generator.py`

---

## 📁 Estructura del proyecto

```
comarb-sentimiento/
├── .github/
│   └── workflows/
│       └── update-report.yml    # GitHub Action (ejecución automática)
├── docs/
│   ├── index.html               # Dashboard HTML (generado automáticamente)
│   └── tweets_data.json         # Datos crudos (generado automáticamente)
├── main.py                      # Script principal de scraping
├── report_generator.py          # Generador del dashboard HTML
├── setup_cookies.py             # Asistente para configurar cookies
├── requirements.txt             # Dependencias Python
├── .gitignore                   # Archivos a ignorar
└── README.md                    # Este archivo
```

---

## 🔧 Uso local

También podés ejecutar el reporte localmente en tu máquina:

```bash
# Instalar dependencias
pip install -r requirements.txt
python -m textblob.download_corpora lite

# Ejecutar (genera docs/index.html)
python main.py
```

En modo local el reporte se abre automáticamente en tu navegador.

---

## 🍪 Mantenimiento de cookies

Las cookies de Twitter expiran periódicamente (cada ~30 días). Si el Action falla:

1. Ejecutá `python setup_cookies.py` en tu máquina
2. Copiá el nuevo base64
3. Actualizá el secret `TWITTER_COOKIES` en GitHub

**Señales de cookies expiradas:**
- El Action falla con "❌ CI Mode: cookies inválidas"
- Error 404 o "unauthorized" en los logs

---

## 🛠 Personalización

### Cambiar horario de ejecución

Editá `.github/workflows/update-report.yml`, línea del `cron`:

```yaml
schedule:
  - cron: '0 11 * * *'  # 11:00 UTC = 08:00 Argentina
```

Formato cron: `minuto hora día-mes mes día-semana`

Ejemplos:
- `'0 14 * * *'` → todos los días a las 11:00 Argentina
- `'0 11 * * 1'` → solo los lunes a las 08:00 Argentina
- `'0 11 * * 1,4'` → lunes y jueves a las 08:00 Argentina

### Cambiar cantidad de tweets

En `main.py`, modificá:
```python
MAX_TWEETS_PER_KEYWORD = 200  # Cambiar a lo que necesites
```

### Agregar/quitar palabras clave

En `main.py`, modificá:
```python
KEYWORDS = ["comarb", "sifere", "sircar", "sirpei", "sircreb", "sircupa", "sirtac"]
```

---

## ⚠️ Notas importantes

- **No subir `twitter_cookies.json`** al repositorio (ya está en `.gitignore`)
- **No compartir el secret** `TWITTER_COOKIES` con nadie
- **GitHub Pages gratis** requiere repositorio público
- **Rate limits**: Twitter puede limitar las búsquedas. El script ya incluye manejo de rate limits con reintentos automáticos
- **Twikit** usa la API interna de Twitter (no la oficial). Funciona gratis pero puede romperse si Twitter cambia sus endpoints

---

## 🐛 Solución de problemas

| Problema | Solución |
|----------|----------|
| Action falla: "cookies inválidas" | Regenerar cookies con `setup_cookies.py` y actualizar el secret |
| Action falla: "rate limit" | Reducir `MAX_TWEETS_PER_KEYWORD` o espaciar más las ejecuciones |
| Action falla: "404" | Actualizar twikit: `pip install twikit --upgrade` y regenerar cookies |
| GitHub Pages no se actualiza | Verificar que Pages esté configurado en main / /docs |
| Reporte vacío | Verificar que las keywords tengan tweets en el período |
| Login falla localmente | Usar método de cookies del navegador (opción 2 en `setup_cookies.py`) |
