"""``python -m ttp_similarity.api`` -- serve the station."""

from __future__ import annotations

import argparse

from .. import config, paths
from ..cli import configure_stdout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serve the TTP similarity station.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--dataset", default=paths.DEFAULT_DATASET, choices=list(paths.KNOWN_DATASETS)
    )
    args = parser.parse_args(argv)

    configure_stdout()
    config.validate()

    import uvicorn

    from .app import create_app

    app = create_app(dataset=args.dataset)
    print(f"İstasyon hazır: http://{args.host}:{args.port}  (veri seti: {args.dataset})")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
