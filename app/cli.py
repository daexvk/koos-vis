from __future__ import annotations

import argparse

from app.core.config import get_settings, set_config_path


def main() -> None:
    parser = argparse.ArgumentParser(prog="koos-back")
    parser.add_argument("--config", help="Path to koos-back JSON config")
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve_parser = subparsers.add_parser("serve", help="Run the API server")
    serve_parser.add_argument("--config", dest="command_config", help=argparse.SUPPRESS)
    serve_parser.add_argument("--host", help="Override server.host from config")
    serve_parser.add_argument("--port", type=int, help="Override server.port from config")

    worker_parser = subparsers.add_parser("subset-worker", help="Run a subset worker process")
    worker_parser.add_argument("--config", dest="command_config", help=argparse.SUPPRESS)

    args, remaining = parser.parse_known_args()
    set_config_path(getattr(args, "command_config", None) or args.config)

    if args.command == "serve":
        _serve(host=args.host, port=args.port)
    elif args.command == "subset-worker":
        _subset_worker(remaining)


def _serve(host: str | None, port: int | None) -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=host or settings.server.host,
        port=port or settings.server.port,
        workers=settings.server.workers,
    )


def _subset_worker(argv: list[str]) -> None:
    from app.services.subset_worker import main as worker_main

    worker_main(argv)


if __name__ == "__main__":
    main()
