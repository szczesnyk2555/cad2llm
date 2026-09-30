"""Minimal upload page: python -m cad2llm.web  ->  http://127.0.0.1:8000"""
import base64
import html
import json
import os
import re
import tempfile
from pathlib import Path

from flask import Flask, render_template_string, request
from markupsafe import Markup

from . import SUPPORTED, CadError, analyze
from .llm import describe

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

STEEL_DENSITY = 7.85  # g/cm3, for the mass estimate shown next to the volume


def fmt(v, digits=2) -> str:
    """Numbers in Polish notation: 70233.445 -> '70 233,45', 80.0 -> '80'."""
    if isinstance(v, str):
        v = float(v)
    s = f"{v:,.{digits}f}" if isinstance(v, float) else f"{v:,}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s.replace(",", " ").replace(".", ",")


def chips(counts: dict, prefix="", suffix="") -> list[str]:
    """{'9.0': 4} -> ['Ø9 ×4']"""
    return [f"{prefix}{fmt(k)}{suffix}" + (f" ×{n}" if n > 1 else "") for k, n in counts.items()]


def summary(d: dict) -> dict:
    """What the page shows: big figures (stats) and groups of values (chips)."""
    stats, groups, lists, warning = [], [], [], None
    if d["format"] == "STEP":
        bb = d["bounding_box_mm"]
        vol_cm3 = d["volume_mm3"] / 1000
        stats = [
            ("Gabaryt", f"{fmt(bb['x'])} × {fmt(bb['y'])} × {fmt(bb['z'])} mm"),
            ("Objętość", f"{fmt(vol_cm3)} cm³"),
            ("Masa (stal)", f"≈ {fmt(vol_cm3 * STEEL_DENSITY / 1000, 3)} kg"),
            ("Powierzchnia", f"{fmt(d['surface_area_mm2'] / 100)} cm²"),
            ("Bryły / ściany / krawędzie", f"{d['solids']} / {d['faces']} / {d['edges']}"),
            ("Jednostki w pliku", d["declared_units"]),
        ]
        groups = [("Średnice (powierzchnie walcowe)", chips(d["cylinder_diameters_mm"], "Ø"))]
    elif d["format"] == "DXF":
        ext = d["extents"]
        stats = [
            ("Obrys rysunku", f"{fmt(ext['width'])} × {fmt(ext['height'])} {d['units']}" if ext else "—"),
            ("Jednostki", d["units"]),
            ("Wymiary na rysunku", str(len(d["dimensions"]))),
            ("Okręgi / łuki", f"{sum(d['circle_diameters'].values())} / {sum(d['arc_radii'].values())}"),
        ]
        groups = [
            ("Wymiary (DIMENSION)", [dm["text"] or fmt(dm["value"]) for dm in d["dimensions"] if dm["value"] is not None or dm["text"]]),
            ("Średnice okręgów", chips(d["circle_diameters"], "Ø")),
            ("Promienie łuków", chips(d["arc_radii"], "R")),
            ("Długości linii", chips(dict(list(d["line_lengths"].items())[:20]))),
            ("Warstwy", d["layers"]),
        ]
        lists = [("Teksty", d["texts"])]
    elif d["format"] == "PDF":
        f = d["found_in_text"]
        page = d["page_sizes_mm"][0] if d["page_sizes_mm"] else None
        stats = [
            ("Rodzaj", "rysunek wektorowy (CAD)" if d["kind"].startswith("vector") else "skan" if d["kind"].startswith("scan") else "dokument tekstowy"),
            ("Strony", str(d["pages"])),
            ("Format strony", f"{fmt(page['width_mm'], 0)} × {fmt(page['height_mm'], 0)} mm" if page else "—"),
            ("Warstwa tekstowa", "tak" if d["text_layer"] else "brak"),
        ]
        labels = {"diameters": "Średnice", "fits": "Pasowania", "tolerances": "Tolerancje", "threads": "Gwinty",
                  "radii": "Promienie", "chamfers": "Fazy", "roughness": "Chropowatość", "angles": "Kąty"}
        groups = [(label, [k + (f" ×{n}" if n > 1 else "") for k, n in f.get(key, {}).items()]) for key, label in labels.items()]
        lists = [("Tekst z rysunku", [line for line in d["text"].splitlines() if line.strip()])]
        if not d["text_layer"]:
            warning = "PDF bez warstwy tekstowej (skan) – wartości odczyta model z obrazu, sprawdź je."
    return {"stats": stats, "groups": [(t, v) for t, v in groups if v], "lists": [(t, v) for t, v in lists if v], "warning": warning}


def markdown(text: str) -> Markup:
    """Tiny Markdown -> HTML for the model's answer (headings, bullets, bold, inline code)."""
    out, in_list = [], False
    for line in html.escape(text).splitlines():
        line = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", line)
        line = re.sub(r"`(.+?)`", r"<code>\1</code>", line)
        if m := re.match(r"\s*[-*] (.*)", line):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{m.group(1)}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        if m := re.match(r"(#{1,4}) (.*)", line):
            out.append(f"<h3>{m.group(2)}</h3>")
        elif line.strip():
            out.append(f"<p>{line}</p>")
    if in_list:
        out.append("</ul>")
    return Markup("\n".join(out))


PAGE = """<!doctype html>
<html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>cad2llm</title>
<style>
  :root { --bg:#f3f4f6; --card:#fff; --line:#dde2e9; --text:#1c2430; --muted:#6b7480; --accent:#e8850c; --chip:#eef3f9; --chip-text:#24507e; }
  * { box-sizing: border-box; }
  body { font: 15px/1.5 system-ui, "Segoe UI", sans-serif; margin: 0; color: var(--text); background: var(--bg); }
  header { background: #18202b; color: #fff; padding: 14px 24px; font-weight: 700; letter-spacing: .5px; }
  header span { color: var(--accent); }
  main { max-width: 1180px; margin: 0 auto; padding: 20px 16px 48px; }
  .card { background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 18px 20px; margin-bottom: 16px; }
  form.card { display: grid; grid-template-columns: 1fr 1fr auto; gap: 12px; align-items: end; }
  label { display: flex; flex-direction: column; gap: 4px; font-size: 13px; color: var(--muted); font-weight: 600; }
  input[type=text] { font: inherit; padding: 8px 10px; border: 1px solid var(--line); border-radius: 6px; }
  .check { flex-direction: row; align-items: center; gap: 6px; grid-column: 1 / -1; font-weight: 500; }
  button { font: inherit; font-weight: 600; padding: 9px 22px; background: var(--accent); color: #fff; border: 0; border-radius: 6px; cursor: pointer; }
  .err { background: #fbe6e3; color: #b0321f; padding: 12px 16px; border-radius: 8px; margin-bottom: 16px; font-weight: 600; }
  .warn { background: #fdf3dc; color: #8a5a10; padding: 10px 14px; border-radius: 8px; margin-bottom: 12px; }
  .head { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; margin-bottom: 14px; }
  .head h2 { margin: 0; font-size: 20px; }
  .badge { background: var(--chip); color: var(--chip-text); border-radius: 999px; padding: 2px 10px; font-size: 12px; font-weight: 700; }
  .grid { display: grid; grid-template-columns: minmax(0, 5fr) minmax(0, 6fr); gap: 20px; }
  .preview img { width: 100%; border: 1px solid var(--line); border-radius: 8px; background: #fff; }
  .stats { display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: 10px; margin-bottom: 14px; }
  .stat { background: #f8f9fb; border: 1px solid var(--line); border-radius: 8px; padding: 10px 12px; }
  .stat small { display: block; color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .4px; }
  .stat b { font-size: 18px; }
  .group { margin-bottom: 12px; }
  .group h4 { margin: 0 0 6px; font-size: 12px; text-transform: uppercase; letter-spacing: .4px; color: var(--muted); }
  .chip { display: inline-block; background: var(--chip); color: var(--chip-text); border-radius: 6px; padding: 3px 9px; margin: 0 4px 4px 0;
          font: 600 13.5px/1.4 ui-monospace, Consolas, monospace; }
  ul.plain { margin: 0; padding-left: 18px; font-size: 14px; }
  .desc h3 { font-size: 15px; margin: 16px 0 4px; color: #24507e; } .desc h3:first-child { margin-top: 0; }
  .desc ul { margin: 4px 0; padding-left: 20px; } .desc p { margin: 4px 0; }
  .meta { color: var(--muted); font-size: 12.5px; margin-top: 12px; }
  details summary { cursor: pointer; color: var(--muted); font-weight: 600; }
  pre { background: #18202b; color: #d9e0e8; padding: 12px; border-radius: 8px; overflow: auto; max-height: 460px; font-size: 12.5px; }
  @media (max-width: 800px) { .grid, form.card { grid-template-columns: 1fr; } }
</style></head><body>
<header>cad2<span>llm</span></header>
<main>
<form class="card" method="post" enctype="multipart/form-data">
  <label>Plik (.step, .stp, .dxf, .pdf)<input type="file" name="file" accept=".step,.stp,.dxf,.pdf" required></label>
  <label>Pytanie (opcjonalnie)<input type="text" name="prompt" value="{{ prompt }}" placeholder="Opisz ten element."></label>
  <button type="submit">Analizuj</button>
  <label class="check"><input type="checkbox" name="dry_run" {{ 'checked' if dry_run }}> tylko pomiary, bez wywołania OpenAI</label>
</form>
{% if error %}<div class="err">{{ error }}</div>{% endif %}
{% if data %}
<section class="card">
  <div class="head"><h2>{{ data.file }}</h2><span class="badge">{{ data.format }}</span></div>
  {% if s.warning %}<div class="warn">{{ s.warning }}</div>{% endif %}
  <div class="grid">
    <div class="preview">{% if image %}<img src="data:image/png;base64,{{ image }}" alt="podgląd">{% endif %}</div>
    <div>
      <div class="stats">{% for label, value in s.stats %}<div class="stat"><small>{{ label }}</small><b>{{ value }}</b></div>{% endfor %}</div>
      {% for title, values in s.groups %}
        <div class="group"><h4>{{ title }}</h4>{% for v in values %}<span class="chip">{{ v }}</span>{% endfor %}</div>
      {% endfor %}
      {% for title, values in s.lists %}
        <div class="group"><h4>{{ title }}</h4><ul class="plain">{% for v in values[:30] %}<li>{{ v }}</li>{% endfor %}</ul></div>
      {% endfor %}
    </div>
  </div>
</section>
{% if answer %}
<section class="card desc">
  {{ answer_html }}
  <div class="meta">{{ answer.model }} · {{ answer.seconds }} s{% if answer.tokens %} · tokeny {{ answer.tokens.input }} / {{ answer.tokens.output }}{% endif %}</div>
</section>
{% endif %}
<section class="card"><details><summary>JSON wysłany do modelu</summary><pre>{{ json }}</pre></details></section>
{% endif %}
</main>
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
                raise CadError(f"Nieobsługiwany typ pliku '{suffix}'. Dozwolone: .step, .stp, .dxf, .pdf (DWG najpierw zapisz jako DXF lub PDF).")
            # extractors need a real file (OpenCascade reads from disk)
            fd, tmp = tempfile.mkstemp(suffix=suffix)
            os.close(fd)
            try:
                upload.save(tmp)
                data, png = analyze(tmp)
            finally:
                os.remove(tmp)
            data["file"] = upload.filename
            ctx.update(data=data, s=summary(data), json=json.dumps(data, indent=2, ensure_ascii=False),
                       image=base64.b64encode(png).decode() if png else None)
            if not ctx["dry_run"]:
                ctx["answer"] = describe(data, png, ctx["prompt"] or None)
                ctx["answer_html"] = markdown(ctx["answer"]["text"])
        except CadError as e:
            ctx["error"] = str(e)
    return render_template_string(PAGE, **ctx)


if __name__ == "__main__":
    app.run(host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "8000")))
