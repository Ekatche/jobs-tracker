import importlib
import sys


def test_app_imports_without_pymupdf(monkeypatch):
    """L'absence de pymupdf ne doit pas empêcher l'API de démarrer."""
    monkeypatch.setitem(sys.modules, "fitz", None)
    for mod in ("app.services.cv_parser", "app.routers.cover_letters"):
        sys.modules.pop(mod, None)
    module = importlib.import_module("app.services.cv_parser")
    assert hasattr(module, "extract_text_from_pdf")
