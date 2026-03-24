"""plugins 包：统一插件能力与注册机制。"""


from plugins.channels.cli import CLIChannelPlugin
from plugins.registry import PluginRegistry
from plugins.tools.time_tool import CurrentTimeToolPlugin

__all__ = [
    "CLIChannelPlugin",
    "CurrentTimeToolPlugin",
    "PluginRegistry",
]


