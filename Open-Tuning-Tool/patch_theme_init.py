with open("fpv_tuner/ui/theme/__init__.py", "r") as f:
    code = f.read()

if "effects" not in code:
    code = code.replace("from fpv_tuner.ui.theme.stylesheet import app_stylesheet", 
                        "from fpv_tuner.ui.theme.stylesheet import app_stylesheet\nfrom fpv_tuner.ui.theme.effects import apply_shadow")
    code = code.replace('"app_stylesheet",', '"app_stylesheet", "apply_shadow",')
    with open("fpv_tuner/ui/theme/__init__.py", "w") as f:
        f.write(code)
