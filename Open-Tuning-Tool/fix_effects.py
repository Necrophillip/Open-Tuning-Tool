with open("fpv_tuner/ui/theme/effects.py", "r") as f:
    code = f.read()

code = code.replace("shadow.setOffset(QPoint(0, y_offset))", "shadow.setOffset(0.0, float(y_offset))")

with open("fpv_tuner/ui/theme/effects.py", "w") as f:
    f.write(code)
