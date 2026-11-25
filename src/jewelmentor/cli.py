"""Cross-platform service and reproducible evaluation entry points."""

import argparse
import asyncio
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(prog="jewelmentor")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="Start the local single-process workbench")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    evaluate = commands.add_parser("evaluate", help="Run versioned offline evaluation")
    evaluate.add_argument("--output", type=Path, default=Path("runtime/evaluation.json"))
    args = parser.parse_args()
    if args.command == "serve":
        import uvicorn

        from jewelmentor.api import create_app

        uvicorn.run(create_app(), host=args.host, port=args.port, workers=1)
    else:
        from jewelmentor.evaluation import evaluate

        report = asyncio.run(evaluate())
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(
            json.dumps(
                {"output": str(args.output), "metrics": report["metrics"]},
                ensure_ascii=True,
                indent=2,
            )
        )
        if report["failures"]:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
