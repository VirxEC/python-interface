import platform
from enum import IntEnum

from rlbot.utils.logging import DEFAULT_LOGGER


class OS(IntEnum):
    UNKNOWN = 0
    WINDOWS = 1
    LINUX = 2


if platform.system() == "Windows":
    MAIN_EXECUTABLE_NAME = "RLBotServer.exe"
    CURRENT_OS = OS.WINDOWS
elif platform.system() == "Linux":
    MAIN_EXECUTABLE_NAME = "RLBotServer"
    CURRENT_OS = OS.LINUX
else:
    DEFAULT_LOGGER.warn("Unknown OS: " + platform.system())
    MAIN_EXECUTABLE_NAME = ""
    CURRENT_OS = OS.UNKNOWN
