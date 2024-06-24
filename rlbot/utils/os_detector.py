import platform
from enum import IntEnum


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
    from rlbot.utils.logging import get_logger

    MAIN_EXECUTABLE_NAME = ""
    CURRENT_OS = OS.UNKNOWN
    get_logger("os_detector").warn("Unknown OS: " + platform.system())
