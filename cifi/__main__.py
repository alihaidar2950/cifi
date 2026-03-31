"""CLI entry point for local testing: python -m cifi <logfile>"""

import asyncio
import json
import sys

from cifi.analyzer import analyze
from cifi.config import Config
from cifi.ingestion import ingest_local
from cifi.preprocessor import preprocess


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m cifi <logfile> [workspace]")
        print("  logfile:   path to a CI log file")
        print("  workspace: path to the repo checkout (default: current dir)")
        sys.exit(1)

    log_path = sys.argv[1]
    workspace = sys.argv[2] if len(sys.argv) > 2 else "."

    try:
        with open(log_path) as f:
            step_logs = f.read()
    except FileNotFoundError:
        print(f"Error: log file not found: {log_path}")
        sys.exit(1)

    config = Config.from_env()
    context = ingest_local(workspace=workspace, step_logs=step_logs)
    processed = preprocess(context, max_tokens=config.max_tokens)
    result = asyncio.run(analyze(processed, config))

    print(json.dumps(result.model_dump(), indent=2))


if __name__ == "__main__":
    main()
