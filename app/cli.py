from __future__ import annotations

import argparse
from threading import Timer
import webbrowser

from app.core.config import get_settings, set_config_path


def main() -> None:
    parser = argparse.ArgumentParser(prog="koos-back")
    parser.add_argument("--config", help="Path to koos-back JSON config")
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve_parser = subparsers.add_parser("serve", help="Run the API server")
    serve_parser.add_argument("--config", dest="command_config", help=argparse.SUPPRESS)
    serve_parser.add_argument("--host", help="Override server.host from config")
    serve_parser.add_argument("--port", type=int, help="Override server.port from config")
    serve_parser.add_argument("--open-browser", action="store_true", default=None, help="Open /koos/ in the default browser after starting")
    serve_parser.add_argument("--no-open-browser", action="store_false", dest="open_browser", help="Do not open a browser")

    worker_parser = subparsers.add_parser("subset-worker", help="Run a subset worker process")
    worker_parser.add_argument("--config", dest="command_config", help=argparse.SUPPRESS)

    watch_parser = subparsers.add_parser("subset-watch", help="Watch subset inputs and run jobs automatically")
    watch_parser.add_argument("--config", dest="command_config", help=argparse.SUPPRESS)
    watch_parser.add_argument("--input-root")
    watch_parser.add_argument("--debounce-seconds", type=float)
    watch_parser.add_argument("--stable-seconds", type=float)
    watch_parser.add_argument("--poll-interval", type=float)
    watch_parser.add_argument("--pattern", action="append", dest="patterns")

    args, remaining = parser.parse_known_args()
    set_config_path(getattr(args, "command_config", None) or args.config)

    if args.command == "serve":
        _serve(host=args.host, port=args.port, open_browser=args.open_browser)
    elif args.command == "subset-worker":
        _subset_worker(remaining)
    elif args.command == "subset-watch":
        _subset_watch(_watch_args(args, remaining))


def _serve(host: str | None, port: int | None, open_browser: bool | None) -> None:
    import uvicorn

    settings = get_settings()
    bind_host = host or settings.server.host
    bind_port = port or settings.server.port
    should_open_browser = settings.server.open_browser if open_browser is None else open_browser

    if should_open_browser:
        _schedule_browser_open(
            settings.server.browser_url or _default_browser_url(bind_host, bind_port)
        )

    uvicorn.run(
        "app.main:app",
        host=bind_host,
        port=bind_port,
        workers=settings.server.workers,
    )


def _subset_worker(argv: list[str]) -> None:
    from app.services.subset_worker import main as worker_main

    worker_main(argv)


def _subset_watch(argv: list[str]) -> None:
    from app.services.subset_watch_service import main as watch_main

    watch_main(argv)


def _watch_args(args, remaining: list[str]) -> list[str]:
    argv = list(remaining)
    if args.input_root is not None:
        argv.extend(["--input-root", args.input_root])
    if args.debounce_seconds is not None:
        argv.extend(["--debounce-seconds", str(args.debounce_seconds)])
    if args.stable_seconds is not None:
        argv.extend(["--stable-seconds", str(args.stable_seconds)])
    if args.poll_interval is not None:
        argv.extend(["--poll-interval", str(args.poll_interval)])
    for pattern in args.patterns or []:
        argv.extend(["--pattern", pattern])
    return argv


def _default_browser_url(host: str, port: int) -> str:
    browser_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    return f"http://{browser_host}:{port}/koos/"


def _schedule_browser_open(url: str) -> None:
    def open_url() -> None:
        try:
            webbrowser.open(url, new=2)
        except Exception as exc:
            print(f"Failed to open browser for {url}: {exc}")

    Timer(1.5, open_url).start()


if __name__ == "__main__":
    main()
