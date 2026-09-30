"""OpenAI Responses API call: measurements JSON as text + preview PNG as image."""
import base64
import json
import os
import time

from dotenv import load_dotenv

from . import CadError

load_dotenv()

DEFAULT_MODEL = "gpt-5.6-luna"

INSTRUCTIONS = """You are an experienced mechanical engineer. You get measurements extracted from a CAD file or a drawing
(exact values in the stated units) and a preview image. Use the extracted numbers; read from the image only what is missing
and say so. For a PDF, "found_in_text" and "text" come from the drawing's text layer (exact); a scan has no text layer.

Answer in Polish (unless the user asks otherwise), in concise Markdown with these sections:
## Co to jest
One or two sentences: what the part probably is and what it is for.
## Wymiary główne
Bullet list: overall size, main diameters / lengths / thickness, with units.
## Cechy
Bullet list: holes, bores, steps, slots, threads, chamfers, radii, fits and tolerances, roughness - with dimensions and counts.
## Materiał i masa
Material if known (drawing / title block); estimated mass if the volume is known (state the assumed density).
## Wykonanie
2-4 bullets: likely manufacturing route and what to watch out for.
## Niepewności
Only if something is unclear or missing."""


def describe(data: dict, png: bytes | None, prompt: str | None = None) -> dict:
    """Returns {"text": markdown, "model", "seconds", "tokens"}."""
    if not os.getenv("OPENAI_API_KEY"):
        raise CadError("Brak OPENAI_API_KEY - wpisz klucz do pliku .env i uruchom ponownie.")
    from openai import OpenAI, OpenAIError

    units = data.get("output_units") or data.get("units")
    content = [{"type": "input_text", "text":
                f"Measurements (units: {units}):\n{json.dumps(data, ensure_ascii=False)}\n\n"
                f"{prompt or 'Opisz ten element.'}"}]
    if png:
        content.append({"type": "input_image", "image_url": "data:image/png;base64," + base64.b64encode(png).decode(),
                        "detail": "high"})

    model = os.getenv("OPENAI_MODEL") or DEFAULT_MODEL
    started = time.perf_counter()
    try:
        response = OpenAI().responses.create(
            model=model,
            instructions=INSTRUCTIONS,
            input=[{"role": "user", "content": content}],
            store=False,
        )
    except OpenAIError as e:
        raise CadError(f"Błąd OpenAI API: {e}") from e
    usage = response.usage
    return {"text": response.output_text, "model": model, "seconds": round(time.perf_counter() - started, 1),
            "tokens": {"input": usage.input_tokens, "output": usage.output_tokens} if usage else None}
