import os
import socket
import stat
import subprocess
from pathlib import Path
from typing import Optional

import psutil

from rlbot.utils.logging import DEFAULT_LOGGER
from rlbot.utils.os_detector import CURRENT_OS, MAIN_EXECUTABLE_NAME, OS

# Generated randomly by Kipje13, and confirmed to have no conflict with any common programs
# https://www.adminsub.net/tcp-udp-port-finder/23233
IDEAL_RLBOT_PORT = 23233

# This is the port that Rocket League will use by default if we cannot override it.
DEFAULT_RLBOT_PORT = 50000


def find_main_executable_path(
    main_executable_path: Path,
) -> tuple[Path, Optional[Path]]:
    main_executable_path = main_executable_path.absolute().resolve()

    # check if the path is a the main executable
    if main_executable_path.is_file():
        return main_executable_path.parent, main_executable_path

    # search subdirectories for the main executable
    for path in main_executable_path.glob("**/*"):
        if path.is_file() and path.name == MAIN_EXECUTABLE_NAME:
            return path.parent, path

    return main_executable_path, None


def launch(main_executable_path: Path):
    directory, path = find_main_executable_path(main_executable_path)

    if path is None or not os.access(path, os.F_OK):
        raise FileNotFoundError(
            f"Unable to find RLBotServer at {path}! Is your antivirus messing you up? Check "
            "https://github.com/RLBot/RLBot/wiki/Antivirus-Notes."
        )

    if not os.access(path, os.X_OK):
        os.chmod(path, stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    if not os.access(path, os.X_OK):
        raise PermissionError(
            "Unable to execute RLBotServer due to file permissions! Is your antivirus messing you up? "
            f"Check https://github.com/RLBot/RLBot/wiki/Antivirus-Notes. The exact path is {path}"
        )

    port = DEFAULT_RLBOT_PORT
    try:
        port = find_usable_port()
    except Exception as e:
        DEFAULT_LOGGER.error(str(e))

    args = [str(path), str(port)]

    DEFAULT_LOGGER.info(f"Launching RLBotServer with args {args}")
    if CURRENT_OS != OS.WINDOWS:
        # Unix only works this way, not sure why. Windows works better with the array, guards against spaces in path.
        args = " ".join(args)
    return subprocess.Popen(args, shell=True, cwd=directory), port


def find_existing_process() -> tuple[Optional[psutil.Process], int]:
    logger = DEFAULT_LOGGER
    for proc in psutil.process_iter():
        try:
            if proc.name() == MAIN_EXECUTABLE_NAME:
                if len(proc.cmdline()) > 1:
                    port = int(proc.cmdline()[1])
                    return proc, port
                logger.error(
                    "Failed to find the RLBot port being used in the process args! "
                    + f"Guessing {IDEAL_RLBOT_PORT}."
                )
                return proc, IDEAL_RLBOT_PORT
        except Exception as e:
            logger.error(
                f"Failed to read the name of a process while hunting for {MAIN_EXECUTABLE_NAME}: {e}"
            )
    return None, IDEAL_RLBOT_PORT


def find_usable_port():
    for port_to_test in range(IDEAL_RLBOT_PORT, 65535):
        if is_port_accessible(port_to_test):
            return port_to_test
    raise PermissionError(
        "Unable to find a usable port for running RLBot! Is your antivirus messing you up? "
        "Check https://github.com/RLBot/RLBot/wiki/Antivirus-Notes"
    )


def is_port_accessible(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", port))
            return True
        except:
            return False
