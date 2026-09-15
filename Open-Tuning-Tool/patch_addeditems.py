with open("fpv_tuner/ui/pages/export_page.py", "r") as f:
    code = f.read()

code = code.replace("for item in list(view.getView().addedItems):", "for item in list(view.getView().listDataItems()):")

with open("fpv_tuner/ui/pages/export_page.py", "w") as f:
    f.write(code)
