import platform
from enum import IntEnum


class OS(IntEnum):
    UNKNOWN = 0
    WINDOWS = 1
    LINUX = 2


match platform.system():
    case "Windows":
        MAIN_EXECUTABLE_NAME = "RLBotServer.exe"
        CURRENT_OS = OS.WINDOWS
    case "Linux":
        MAIN_EXECUTABLE_NAME = "RLBotServer"
        CURRENT_OS = OS.LINUX
    case _ as unknown_os:
        from rlbot.utils.logging import get_logger

        MAIN_EXECUTABLE_NAME = ""
        CURRENT_OS = OS.UNKNOWN

        get_logger("os_detector").warning("Unknown OS: %s", unknown_os)
