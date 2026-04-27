import uvicorn

from .app.app import app
from .app.config import get_settings


def main() -> None:
    settings = get_settings()

    # 直接传入 app 对象，确保应用导入发生在 uvicorn 启动事件循环之前，
    # 避免字符串导入路径在 loop 内解析时触发初始化冲突。
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
    )
