with open("fpv_tuner/ui/wizard_shell.py", "r") as f:
    code = f.read()

target = """WIZARD_STEPS = [
    {"title": "Load Log",    "subtitle": "Drop a blackbox log file"},
    {"title": "Analysis",    "subtitle": "Automatic noise analysis"},
    {"title": "Diagnosis",   "subtitle": "Filters & Noise"},
    {"title": "Tuning",      "subtitle": "PID & FF Engine"},
    {"title": "Export",      "subtitle": "Get your new configuration"},
    {"title": "Iterate",     "subtitle": "Fly, log, repeat"},
]"""

replacement = """WIZARD_STEPS = [
    {"title": "Cargar",      "subtitle": "Blackbox log"},
    {"title": "Análisis",    "subtitle": "Procesamiento matemático"},
    {"title": "Diagnóstico", "subtitle": "Filtros y Ruido"},
    {"title": "Tuning",      "subtitle": "PIDs y Feedforward"},
    {"title": "Exportar",    "subtitle": "Obtén la configuración"},
    {"title": "Iterar",      "subtitle": "Vuela, loguea, repite"},
]"""

code = code.replace(target, replacement)
with open("fpv_tuner/ui/wizard_shell.py", "w") as f:
    f.write(code)
