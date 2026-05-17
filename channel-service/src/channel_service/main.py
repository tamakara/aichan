import uvicorn

from .app import app
from .config import get_settings


def main() -> None:
    settings = get_settings()

    uvicorn.run(
        app,
        host=settings.server.host,
        port=settings.server.port,
    )


if __name__ == "__main__":
    main()
