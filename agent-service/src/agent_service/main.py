import uvicorn

from .app.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "agent_service.app.app:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
    )


if __name__ == "__main__":
    main()
