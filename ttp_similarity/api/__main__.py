"""``python -m ttp_similarity.api`` -- serve the station."""

from __future__ import annotations

import argparse

from .. import config, paths, storage
from ..cli import configure_stdout


def ensure_built(dataset: str, auto_build: bool) -> bool:
    """Make sure the dataset and engine artefacts exist, building them if allowed."""
    workspace = paths.Workspace.get(dataset)
    if storage.dataset_exists(workspace) and storage.engine_exists(workspace):
        return True
    if not auto_build:
        print(
            f"'{dataset}' veri seti ya da motor artefaktları eksik. Önce şunları çalıştırın:\n"
            f"  python -m ttp_similarity.data.build --dataset {dataset}\n"
            f"  python -m ttp_similarity.engine.build --dataset {dataset}\n"
            "ya da sunucuyu --auto-build ile başlatın."
        )
        return False
    from ..data.build import build_dataset
    from ..engine.build import build_engine

    paths.ensure_base_dirs()
    if not storage.dataset_exists(workspace):
        print(f"[istasyon] '{dataset}' veri seti derleniyor...")
        build_dataset(dataset)
    print(f"[istasyon] '{dataset}' motor artefaktları derleniyor...")
    build_engine(dataset)
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serve the TTP similarity station.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--dataset", default=paths.DEFAULT_DATASET, choices=list(paths.KNOWN_DATASETS)
    )
    parser.add_argument(
        "--auto-build",
        action="store_true",
        help="build the dataset and engine first when they are missing",
    )
    args = parser.parse_args(argv)

    configure_stdout()
    config.validate()
    if not ensure_built(args.dataset, args.auto_build):
        return 2

    import uvicorn

    from .app import WEB_DIST, create_app

    if not (WEB_DIST / "index.html").exists():
        print("[istasyon] Uyarı: arayüz derlenmemiş (web/dist yok); yalnızca API sunuluyor.")
        print("           Derlemek için: cd web && npm ci && npm run build")
    app = create_app(dataset=args.dataset)
    print(f"İstasyon hazır: http://{args.host}:{args.port}  (veri seti: {args.dataset})")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
