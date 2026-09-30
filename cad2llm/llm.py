"""OpenAI Responses API call: measurements JSON as text + preview PNG as image."""
import base64
import json
import os

from dotenv import load_dotenv

from . import CadError

load_dotenv()

INSTRUCTIONS = (
    "You are an experienced mechanical engineer. You get measurements extracted from a CAD file "
    "(exact values, in the units stated) and a preview image. Describe the part: what it probably is, "
    "overall size, main features (holes, bores, steps, slots) with their dimensions, and anything notable "
    "for manufacturing. Use the extracted numbers, not estimates from the image. "
    "Answer in Polish unless the user asks otherwise."
)


def describe(data: dict, png: bytes | None, prompt: str | None = None) -> str:
    if not os.getenv("OPENAI_API_KEY"):
        raise CadError("OPENAI_API_KEY is not set (put it in .env or the environment).")
    from openai import OpenAI, OpenAIError

    units = data.get("output_units") or data.get("units")
    content = [{"type": "input_text", "text":
                f"Measurements (units: {units}):\n{json.dumps(data, ensure_ascii=False)}\n\n"
                f"{prompt or 'Describe this part.'}"}]
    if png:
        content.append({"type": "input_image", "image_url": "data:image/png;base64," + base64.b64encode(png).decode()})

    try:
        response = OpenAI().responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-6-astra"),
            instructions=INSTRUCTIONS,
            input=[{"role": "user", "content": content}],
            store=False,
        )
    except OpenAIError as e:
        raise CadError(f"OpenAI API error: {e}") from e
    return response.output_text
