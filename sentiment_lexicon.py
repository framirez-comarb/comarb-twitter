"""
═══════════════════════════════════════════════════════════════
  Léxico de sentimiento para español argentino
  Orientado a tweets sobre sistemas tributarios (COMARB, SIFERE, etc.)
═══════════════════════════════════════════════════════════════

Pesos:
  0.5 = leve      1.0 = estándar
  1.5 = fuerte    2.0 = muy fuerte
"""

# ─────────────────────────────────────────────────────────────
#  PALABRAS NEGATIVAS (individuales)
# ─────────────────────────────────────────────────────────────
NEGATIVE_WORDS = {
    # ── Fallas de sistema / técnicas ──
    "error": 1.0, "falla": 1.0, "bug": 1.0, "caída": 1.0, "crash": 1.0,
    "cuelga": 1.0, "traba": 1.0, "tilt": 1.0, "tilteado": 1.0,
    "lento": 0.7, "lentísimo": 1.5, "lentisimo": 1.5, "demora": 0.7,
    "tarda": 0.7, "lagueado": 1.0, "bugueado": 1.0, "roto": 1.0,
    "caído": 1.0, "colgado": 1.0, "trabado": 1.0,

    # ── Frustración leve ──
    "molesta": 0.7, "molesto": 0.7, "complicado": 0.5, "pesado": 0.5,
    "engorroso": 0.7, "tedioso": 0.7, "confuso": 0.5, "difícil": 0.5,
    "incómodo": 0.5, "aburrido": 0.5,

    # ── Frustración fuerte ──
    "harto": 1.5, "cansado": 1.0, "podrido": 1.5, "hinchado": 1.5,
    "saturado": 1.0, "agotado": 1.0, "quemado": 1.0, "reventado": 1.0,
    "caliente": 1.0, "sacado": 1.5, "indignado": 1.5, "furioso": 1.5,
    "enfurecido": 1.5, "frustración": 1.0, "frustrado": 1.0,
    "desesperado": 1.5, "desesperante": 1.5,

    # ── Quejas / reclamos ──
    "queja": 1.0, "reclamo": 1.0, "problema": 0.7, "problemón": 1.5,
    "quilombo": 1.5, "bardo": 1.0, "lío": 0.7, "desastre": 1.5,
    "catástrofe": 2.0, "caos": 1.5, "papelón": 1.5, "bochorno": 1.0,
    "escándalo": 1.5, "disparate": 1.5, "locura": 1.0, "delirio": 1.5,
    "demencial": 1.5,

    # ── Calificativos negativos ──
    "horrible": 1.5, "pésimo": 1.5, "malo": 1.0, "peor": 1.5,
    "espantoso": 1.5, "nefasto": 2.0, "deplorable": 2.0, "lamentable": 1.5,
    "vergonzoso": 1.5, "vergüenza": 1.5, "patético": 1.5, "ridículo": 1.0,
    "mediocre": 1.0, "penoso": 1.0, "pobre": 0.5, "flojo": 0.5,
    "berreta": 1.0, "choto": 1.5, "trucho": 1.0, "cualquiera": 0.7,

    # ── Insultos argentinos (leves) ──
    "inútil": 1.5, "inservible": 1.5, "incapaz": 1.0, "incompetente": 1.5,
    "impresentable": 1.5, "payaso": 1.0, "dinosaurio": 1.0, "dinosaurios": 1.0,
    "vago": 0.7, "ladri": 1.0, "chanta": 1.5, "chamuyero": 1.0,
    "enano": 1.0, "vende humo": 1.5, "atorrante": 1.0, "sinvergüenza": 1.5,

    # ── Insultos argentinos (fuertes) ──
    "mierda": 2.0, "porquería": 2.0, "basura": 2.0, "garcha": 2.0,
    "pija": 1.5, "pelotudo": 2.0, "pelotuda": 2.0, "pelotudez": 2.0,
    "boludo": 1.0, "boluda": 1.0, "boludez": 1.0, "forro": 2.0,
    "forra": 2.0, "gil": 1.5, "gila": 1.5, "gilada": 1.5,
    "cagada": 1.5, "cagón": 1.5, "ortiva": 1.0, "rata": 1.0,
    "sorete": 2.0, "imbécil": 2.0, "idiota": 1.5, "tarado": 1.5,
    "mogólico": 2.0, "zapato": 1.0, "cabeza": 0.7, "mersa": 1.0,

    # ── Lunfardo / jerga ──
    "afano": 1.5, "afanar": 1.5, "curro": 1.5, "truchada": 1.5,
    "choreo": 1.5, "chorearon": 1.5, "garchan": 2.0, "cagar": 1.5,
    "cagaron": 1.5, "empomar": 1.5, "empomaron": 1.5, "afanaron": 1.5,

    # ── Robo / corrupción ──
    "robo": 1.5, "roba": 1.5, "roban": 1.5, "chorros": 2.0, "chorro": 2.0,
    "estafa": 2.0, "estafan": 2.0, "ladrones": 2.0, "ladrón": 2.0,
    "mafia": 2.0, "corrupto": 2.0, "corruptos": 2.0, "ñoqui": 1.0, "ñoquis": 1.0,

    # ── Siglas / internet argentino ──
    "lpqlp": 2.0, "hdp": 2.0, "lpm": 2.0, "ctm": 2.0,
    "smh": 1.0, "wtf": 1.0,

    # ── Tributario / COMARB específico ──
    "multa": 1.0, "intimación": 1.5, "deuda": 1.0, "apremio": 1.5,
    "vencido": 1.0, "rechazado": 1.0, "incompatible": 0.7,
    "burocracia": 1.0, "burocrático": 1.0, "trámite": 0.5,
    "obsoleto": 1.5, "desactualizado": 1.0, "anticuado": 1.0,
    "embargado": 1.5, "embargo": 1.5, "sanción": 1.5,

    # ── Rechazo / odio ──
    "odio": 2.0, "detesto": 2.0, "asco": 2.0, "repugnante": 2.0,
    "asqueroso": 2.0, "bronca": 1.5, "rabia": 1.5, "renegando": 1.5,
    "renegar": 1.0, "reniego": 1.0, "pudrirse": 1.5,
}

# ─────────────────────────────────────────────────────────────
#  PALABRAS POSITIVAS (individuales)
# ─────────────────────────────────────────────────────────────
POSITIVE_WORDS = {
    # ── Aprobación general ──
    "bueno": 0.7, "bien": 0.7, "correcto": 0.7, "ok": 0.5,
    "funciona": 0.7, "anda": 0.7, "sirve": 0.7, "anduvo": 0.7,
    "funcionó": 0.7, "resuelto": 1.0, "solucionado": 1.0,

    # ── Aprobación fuerte ──
    "excelente": 1.5, "genial": 1.5, "perfecto": 1.5, "impecable": 1.5,
    "espectacular": 1.5, "increíble": 1.5, "fantástico": 1.5,
    "maravilloso": 1.5, "brillante": 1.5, "sobresaliente": 1.5,
    "extraordinario": 1.5, "notable": 1.0, "destacado": 1.0,

    # ── Argentinismos de aprobación ──
    "copado": 1.0, "copada": 1.0, "piola": 1.0, "groso": 1.5,
    "grosa": 1.5, "grosso": 1.5, "grossa": 1.5, "crack": 1.5,
    "capo": 1.0, "capa": 1.0, "fenómeno": 1.0, "fenomenal": 1.5,
    "bárbaro": 1.0, "mortal": 1.5, "zarpado": 1.5, "zarpada": 1.5,
    "golazo": 1.5, "bomba": 1.0, "masa": 1.0, "fierro": 1.0,
    "joya": 1.0, "genia": 1.5, "genio": 1.5, "ídolo": 1.5,
    "macanudo": 1.0, "macanuda": 1.0, "pipi cucú": 1.0,
    "potable": 0.7, "pasable": 0.5, "safable": 0.5, "rescatable": 0.7,
    "pintón": 0.7, "polenta": 1.0, "power": 0.7,

    # ── Mejora / progreso ──
    "mejoró": 1.0, "mejor": 0.7, "mejorando": 0.7, "avanzó": 1.0,
    "avanza": 0.7, "progreso": 1.0, "solucionaron": 1.0, "arreglaron": 1.0,
    "actualizaron": 0.7, "optimizaron": 1.0, "modernizaron": 1.0,
    "corrigieron": 1.0,

    # ── Gratitud / alivio ──
    "gracias": 1.0, "agradezco": 1.0, "agradecido": 1.0, "agradecida": 1.0,
    "bendición": 1.0, "salvador": 1.0, "salvavidas": 1.0,

    # ── Funcionalidad / practicidad ──
    "rápido": 0.7, "fácil": 0.7, "práctico": 0.7, "útil": 0.7,
    "simple": 0.7, "claro": 0.5, "intuitivo": 0.7, "cómodo": 0.7,
    "ágil": 0.7, "eficiente": 1.0, "eficaz": 1.0, "efectivo": 0.7,
    "accesible": 0.7,

    # ── Afirmación entusiasta ──
    "dale": 0.5, "vamos": 0.7, "vamooo": 1.0, "vamoo": 1.0,
    "bieeeen": 1.0, "siiii": 1.0, "esooo": 1.0, "tamos": 0.7,
}

# ─────────────────────────────────────────────────────────────
#  FRASES NEGATIVAS (multi-palabra)
# ─────────────────────────────────────────────────────────────
NEGATIVE_PHRASES = {
    # ── Fallas de sistema ──
    "no funciona": 1.5, "no anda": 1.5, "no sirve": 1.5,
    "no carga": 1.5, "no cambia": 1.0, "no funcione": 1.5,
    "no me deja": 1.0, "no se puede": 1.0, "no puedo": 1.0,
    "no abre": 1.0, "no entra": 1.0, "no responde": 1.0,
    "se cayó": 1.5, "se cae": 1.5, "se trabó": 1.5, "se traba": 1.5,
    "se colgó": 1.5, "se cuelga": 1.5, "se tilteó": 1.5,
    "se rompió": 1.5, "se bugueó": 1.5,
    "tira error": 1.5, "da error": 1.5, "me tira error": 1.5,
    "página caída": 1.5, "página en mantenimiento": 1.0,
    "fuera de servicio": 1.5, "sin servicio": 1.5,
    "pantalla en blanco": 1.0, "error de carga": 1.5,
    "sistema obsoleto": 1.5, "sistema caído": 1.5,

    # ── Expresiones argentinas de rechazo ──
    "ni en pedo": 1.5, "ni a palos": 1.5, "ni ahí": 1.0,
    "ni loco": 1.0, "ni loca": 1.0, "ni empedo": 1.5,
    "no tienen bolas": 2.0, "faltan huevos": 2.0,
    "alta paja": 1.5, "alta cagada": 2.0, "alto bardo": 1.5,
    "alto quilombo": 2.0, "un desastre": 1.5, "es un asco": 2.0,
    "una porquería": 2.0, "una mierda": 2.0, "una basura": 2.0,
    "una garcha": 2.0, "una cagada": 2.0, "un chiste": 1.5,
    "me tiene harto": 2.0, "me tiene podrido": 2.0,
    "me tienen harto": 2.0, "me tienen podrido": 2.0,
    "me cansé": 1.5, "ya fue": 1.0, "para el orto": 2.0,
    "como el orto": 2.0, "como la mierda": 2.0,
    "una vergüenza": 2.0, "un papelón": 1.5,
    "me quiero matar": 1.5, "me pega un tiro": 1.5,
    "manga de": 1.5, "son unos": 1.0,

    # ── Tributario / COMARB ──
    "se trabó sifere": 2.0, "no me deja cargar": 1.5,
    "no me deja presentar": 1.5, "no puedo presentar": 1.5,
    "no puedo cargar": 1.5, "venció el plazo": 1.0,
}

# ─────────────────────────────────────────────────────────────
#  FRASES POSITIVAS (multi-palabra)
# ─────────────────────────────────────────────────────────────
POSITIVE_PHRASES = {
    "muy bien": 1.0, "todo bien": 0.7, "está bien": 0.5,
    "de diez": 1.5, "de 10": 1.5, "un 10": 1.5,
    "a pleno": 1.0, "a full": 1.0, "al toque": 0.7,
    "por fin": 1.0, "al fin": 1.0, "menos mal": 1.0, "era hora": 1.0,
    "me salvó": 1.5, "me salvaste": 1.5, "me re sirvió": 1.5,
    "de lujo": 1.5, "una masa": 1.5, "la rompió": 1.5,
    "la rompe": 1.5, "anda joya": 1.5, "anda barbaro": 1.5,
    "anda de diez": 1.5, "funciona bien": 1.0, "funciona perfecto": 1.5,
    "anduvo bien": 1.0, "anduvo joya": 1.5,
    "muy útil": 1.0, "muy práctico": 1.0, "muy fácil": 1.0,
    "re piola": 1.5, "re copado": 1.5, "re copada": 1.5,
    "todo ok": 0.7, "cero drama": 1.0, "cero problemas": 1.0,
    "se solucionó": 1.0, "ya anda": 1.0, "ya funciona": 1.0,
    "buena onda": 1.0,
}

# ─────────────────────────────────────────────────────────────
#  NEGACIONES (invierten polaridad del siguiente token)
# ─────────────────────────────────────────────────────────────
NEGATIONS = {"no", "ni", "nunca", "jamás", "jamas", "tampoco", "nadie", "nada", "sin"}

# ─────────────────────────────────────────────────────────────
#  INTENSIFICADORES (multiplican el peso de la siguiente palabra)
# ─────────────────────────────────────────────────────────────
INTENSIFIERS = {
    "re": 1.5,
    "muy": 1.3,
    "super": 1.5, "súper": 1.5,
    "recontra": 2.0,
    "requete": 1.8,
    "tremendo": 1.5, "tremenda": 1.5,
    "terrible": 1.5,      # en Argentina es intensificador: "terrible quilombo"
    "alto": 1.5, "alta": 1.5,  # "alto desastre", "alta paja"
    "banda": 1.3,          # "tarda banda"
    "posta": 1.2,          # "posta que es un desastre"
    "mal": 1.3,            # "me molesta mal" (postfijo)
    "demasiado": 1.3,
    "totalmente": 1.3,
    "completamente": 1.3,
    "absolutamente": 1.3,
}

# ─────────────────────────────────────────────────────────────
#  MARCADORES DE SARCASMO
#  Si co-ocurren con palabras negativas en el mismo tweet,
#  se neutraliza su aporte positivo.
# ─────────────────────────────────────────────────────────────
SARCASM_MARKERS = {
    "joya", "dale", "divino", "divina",
    "hermoso", "hermosa", "brillante",
    "fenómeno", "bárbaro", "genio", "genia",
    "maravilloso", "maravillosa",
}
