#!/usr/bin/env python3
"""
Clasificador de sentimiento v2 — basado en pysentimiento (RoBERTuito).

Reemplaza al `analyze_sentiment` de main.py (lexicon + TextBlob).
Mantiene la misma firma de salida (sentiment string + score float)
para no romper el resto del pipeline.

Mejoras vs v1:
  • Modelo neuronal contextual entrenado en 500M tweets en español
    → captura sarcasmo, lunfardo, puteadas catárticas e insultos
      como descarga, no como insulto al destinatario.
  • Reglas duras complementarias:
      - Cuentas institucionales (@comarb, @ARCA_informa, etc.)
        siempre se fuerzan a NEU (son comunicados oficiales).
"""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from typing import Optional

# Silenciar logs de transformers/HF
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

# UTF-8 en Windows para evitar UnicodeEncodeError en prints con emojis
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


# ── Cuentas cuya voz no expresa opinión sobre los sistemas → forzar NEU ──
# Dos categorías:
#   1) Institucionales: organismos oficiales (comunican normativa)
#   2) Informativas: medios/blogs profesionales del sector contable
# Pueden agregarse a medida que aparezcan más en el corpus.
NEUTRAL_USERNAMES = {
    # — Institucionales —
    "comarb",
    "arca_informa",
    "agipbsas",
    "atmrosario",
    "atermendoza",
    "caat_arg",
    "consejocaba",
    "consejosalta",
    "rentas_pba",
    # — Informativas (medios/blogs/portales del sector) —
    "contadoresenred",
    "blogdelcontador",
    "errepar",
    "webtributario",
    "webtribuno",
}

# Alias retro-compatible (por si algún script lo importa con el nombre viejo)
INSTITUTIONAL_USERNAMES = NEUTRAL_USERNAMES

# Mapeo del output de pysentimiento al vocabulario del proyecto
_LABEL_MAP = {"POS": "positivo", "NEU": "neutro", "NEG": "negativo"}


@lru_cache(maxsize=1)
def _get_analyzer():
    """Carga perezosa del modelo (~500MB la primera vez, después en cache HF)."""
    from pysentimiento import create_analyzer
    return create_analyzer(task="sentiment", lang="es")


def classify(text: str, username: Optional[str] = None) -> dict:
    """
    Clasifica un tweet y devuelve toda la información disponible.

    Args:
        text:     contenido del tweet.
        username: handle del autor sin '@' (opcional, habilita reglas).

    Returns:
        dict con keys:
            sentiment   → "positivo" | "neutro" | "negativo"
            score       → float en [-1, 1] (POS_proba - NEG_proba)
            confidence  → float en [0, 1] (proba de la clase elegida)
            probas      → {"positivo": p, "neutro": p, "negativo": p}
            rule        → str | None (ej. "institutional_account")
    """
    text_clean = (text or "").strip()
    if not text_clean:
        return {
            "sentiment": "neutro",
            "score": 0.0,
            "confidence": 1.0,
            "probas": {"positivo": 0.0, "neutro": 1.0, "negativo": 0.0},
            "rule": "empty_text",
        }

    # ── Regla 1: cuenta institucional → NEU forzado ──
    if username:
        if username.lstrip("@").lower() in INSTITUTIONAL_USERNAMES:
            return {
                "sentiment": "neutro",
                "score": 0.0,
                "confidence": 1.0,
                "probas": {"positivo": 0.0, "neutro": 1.0, "negativo": 0.0},
                "rule": "institutional_account",
            }

    # ── Modelo neuronal ──
    analyzer = _get_analyzer()
    result = analyzer.predict(text_clean)
    probas_raw = result.probas  # {"POS": .., "NEU": .., "NEG": ..}

    probas = {
        "positivo": float(probas_raw["POS"]),
        "neutro": float(probas_raw["NEU"]),
        "negativo": float(probas_raw["NEG"]),
    }
    sentiment = _LABEL_MAP[result.output]
    score = round(probas["positivo"] - probas["negativo"], 3)
    confidence = round(max(probas.values()), 3)

    return {
        "sentiment": sentiment,
        "score": score,
        "confidence": confidence,
        "probas": {k: round(v, 3) for k, v in probas.items()},
        "rule": None,
    }


def classify_batch(texts: list[str]) -> list[dict]:
    """Versión batch — más rápida que llamar classify() en loop."""
    if not texts:
        return []
    analyzer = _get_analyzer()
    results = analyzer.predict(texts)
    out = []
    for r in results:
        probas = {
            "positivo": float(r.probas["POS"]),
            "neutro": float(r.probas["NEU"]),
            "negativo": float(r.probas["NEG"]),
        }
        out.append({
            "sentiment": _LABEL_MAP[r.output],
            "score": round(probas["positivo"] - probas["negativo"], 3),
            "confidence": round(max(probas.values()), 3),
            "probas": {k: round(v, 3) for k, v in probas.items()},
            "rule": None,
        })
    return out


# Compatibilidad con el código viejo: misma firma que analyze_sentiment(text)
def analyze_sentiment_v2(text: str, username: Optional[str] = None):
    """Drop-in para el viejo `analyze_sentiment` de main.py.

    Devuelve (sentiment, score, emoji_details=[]). Los emojis quedan vacíos
    porque ahora la decisión es del modelo; el conteo de emojis sigue
    estando disponible aparte vía main.count_emojis() para estadísticas.
    """
    res = classify(text, username=username)
    return res["sentiment"], res["score"], []


if __name__ == "__main__":
    # Smoke test
    pruebas = [
        ("la concha de la lora no anda sifere", None),
        ("@comarb GRACIAS por todo el trabajo", "usuario_random"),
        ("NOVEDADES COMARB: A partir de 1/4 entra en vigencia el Domicilio Fiscal", "comarb"),
        ("no me digas, pensé que la COMARB coordinaba con ARCA, no dudo que tenés razón", None),
    ]
    for txt, user in pruebas:
        r = classify(txt, username=user)
        print(f"{r['sentiment']:9} conf={r['confidence']:.2f} rule={r['rule']} | {txt[:80]}")
