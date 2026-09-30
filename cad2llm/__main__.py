"""CLI: python -m cad2llm <file> [--prompt "..."] [--no-image] [--dry-run]"""
import argparse
import json
import sys
from pathlib import Path

from . import CadError, analyze


def main() -> int:
    p = argparse.ArgumentParser(prog="cad2llm", description="Extract measurements from a STEP/DXF file and ask OpenAI to describe the part.")
    p.add_argument("file", type=Path)
    p.add_argument("--prompt", help="question for the model (default: describe the part)")
    p.add_argument("--no-image", action="store_true", help="do not render / send a preview image")
    p.add_argument("--dry-run", action="store_true", help="print the extracted JSON, do not call the API")
    args = p.parse_args()

    try:
        if not args.file.is_file():
            raise CadError(f"File not found: {args.file}")
        data, png = analyze(args.file, image=not args.no_image and not args.dry_run)
        if args.dry_run:
            print(json.dumps(data, indent=2, ensure_ascii=False))
            return 0
        from .llm import describe
        print(describe(data, png, args.prompt))
        return 0
    except CadError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
