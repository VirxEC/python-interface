import os
import socket
import stat
import subprocess
from pathlib import Path
from typing import Optional

import psutil

from rlbot.interface import RLBOT_SERVER_PORT
from rlbot.utils.logging import DEFAULT_LOGGER


def find_main_executable_path(
    main_executable_path: Path, main_executable_name: str
) -> tuple[Path, Optional[Path]]:
    main_executable_path = main_executable_path.absolute().resolve()

    # check if the path is directly to the main executable
    if main_executable_path.is_file():
        return main_executable_path.parent, main_executable_path

    # search subdirectories for the main executable
    for path in main_executable_path.glob(f"**/{main_executable_name}"):
        if path.is_file():
            return path.parent, path

    return main_executable_path, None


def is_port_accessible(port: int):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", port))
            return True
        except:
            return False


def find_open_server_port() -> int:
    for port in range(RLBOT_SERVER_PORT, 65535):
        if is_port_accessible(port):
            return port

    raise PermissionError(
        "Unable to find a usable port for running RLBot! Is your antivirus messing you up? "
        "Check https://github.com/RLBot/RLBot/wiki/Antivirus-Notes"
    )


def launch(
    main_executable_path: Path, main_executable_name: str
) -> tuple[subprocess.Popen, int]:
    directory, path = find_main_executable_path(
        main_executable_path, main_executable_name
    )

    if path is None or not os.access(path, os.F_OK):
        raise FileNotFoundError(
            f"Unable to find RLBotServer at '{main_executable_path}'. "
            "Is your antivirus messing you up? Check "
            "https://github.com/RLBot/RLBot/wiki/Antivirus-Notes."
        )

    if not os.access(path, os.X_OK):
        os.chmod(path, stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    if not os.access(path, os.X_OK):
        raise PermissionError(
            "Unable to execute RLBotServer due to file permissions! Is your antivirus messing you up? "
            f"Check https://github.com/RLBot/RLBot/wiki/Antivirus-Notes. The exact path is {path}"
        )

    port = find_open_server_port()
    args = str(path) + " " + str(port)
    DEFAULT_LOGGER.info("Launching RLBotServer with via %s", args)

    return subprocess.Popen(args, shell=True, cwd=directory), port


def find_server_process(
    main_executable_name: str,
) -> tuple[Optional[psutil.Process], int]:
    logger = DEFAULT_LOGGER
    for proc in psutil.process_iter():
        try:
            if proc.name() != main_executable_name:
                continue

            args = proc.cmdline()

            if len(args) < 2:
                # server has no specified port, return default
                return proc, RLBOT_SERVER_PORT

            # read the port
            port = int(proc.cmdline()[-1])
            return proc, port
        except Exception as e:
            logger.error(
                "Failed to read the name of a process while hunting for %s: %s",
                main_executable_name,
                e,
            )

    return None, RLBOT_SERVER_PORT
