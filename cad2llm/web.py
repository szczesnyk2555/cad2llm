"""Minimal upload page: python -m cad2llm.web  ->  http://127.0.0.1:8000"""
import base64
import json
import os
import tempfile
from pathlib import Path

from flask import Flask, render_template_string, request

from . import SUPPORTED, CadError, analyze
from .llm import describe

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

PAGE = """<!doctype html>
<html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>cad2llm</title>
<style>
  body { font: 15px/1.5 system-ui, sans-serif; max-width: 960px; margin: 0 auto; padding: 24px 16px; color: #1c2430; background: #f4f5f7; }
  form, section { background: #fff; border: 1px solid #dde2e9; border-radius: 8px; padding: 16px; margin-bottom: 16px; }
  textarea { width: 100%; font: inherit; box-sizing: border-box; }
  button { font: inherit; font-weight: 600; padding: 8px 18px; background: #e8850c; color: #fff; border: 0; border-radius: 6px; cursor: pointer; }
  pre { background: #18202b; color: #d9e0e8; padding: 12px; border-radius: 6px; overflow: auto; max-height: 420px; font-size: 12.5px; }
  img { max-width: 100%; border: 1px solid #dde2e9; border-radius: 6px; }
  .err { color: #c0392b; font-weight: 600; } .desc { white-space: pre-wrap; } label { display: block; margin: 8px 0; }
</style></head><body>
<h1>cad2llm</h1>
<form method="post" enctype="multipart/form-data">
  <label>Plik CAD (.step, .stp, .dxf) <input type="file" name="file" accept=".step,.stp,.dxf" required></label>
  <label>Pytanie (opcjonalnie)<textarea name="prompt" rows="2" placeholder="Opisz ten element.">{{ prompt }}</textarea></label>
  <label><input type="checkbox" name="dry_run" {{ 'checked' if dry_run }}> tylko pomiary (bez wywołania OpenAI)</label>
  <button type="submit">Analizuj</button>
</form>
{% if error %}<p class="err">{{ error }}</p>{% endif %}
{% if data %}
<section><h2>{{ data.file }}</h2>
  {% if description %}<div class="desc">{{ description }}</div>{% endif %}
  {% if image %}<p><img src="data:image/png;base64,{{ image }}" alt="podgląd"></p>{% endif %}
  <h3>Pomiary wysłane do modelu</h3><pre>{{ json }}</pre>
</section>
{% endif %}
</body></html>"""


@app.route("/", methods=["GET", "POST"])
def index():
    ctx = {"prompt": "", "dry_run": False}
    if request.method == "POST":
        upload = request.files.get("file")
        ctx["prompt"] = request.form.get("prompt", "").strip()
        ctx["dry_run"] = "dry_run" in request.form
        suffix = Path(upload.filename or "").suffix.lower() if upload else ""
        try:
            if not upload or not upload.filename:
                raise CadError("Wybierz plik.")
            if suffix not in SUPPORTED:
                raise CadError(f"Nieobsługiwany typ pliku '{suffix}'. Dozwolone: .step, .stp, .dxf (DWG najpierw zapisz jako DXF).")
            # extractors need a real file (OpenCascade reads from disk)
            fd, tmp = tempfile.mkstemp(suffix=suffix)
            os.close(fd)
            try:
                upload.save(tmp)
                data, png = analyze(tmp)
            finally:
                os.remove(tmp)
            data["file"] = upload.filename
            ctx.update(data=data, json=json.dumps(data, indent=2, ensure_ascii=False),
                       image=base64.b64encode(png).decode() if png else None)
            if not ctx["dry_run"]:
                ctx["description"] = describe(data, png, ctx["prompt"] or None)
        except CadError as e:
            ctx["error"] = str(e)
    return render_template_string(PAGE, **ctx)


if __name__ == "__main__":
    app.run(host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "8000")))
