import uvicorn

from .app import app
from .config import get_settings


def main() -> None:
    settings = get_settings()

    uvicorn.run(
        app,
        host=settings.hub_host,
        port=settings.hub_port,
        log_level=settings.hub_log_level,
    )


if __name__ == "__main__":
    main()
