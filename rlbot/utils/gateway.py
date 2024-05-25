import os
import stat
import subprocess
from pathlib import Path
from typing import Optional

import psutil

from rlbot.utils.logging import DEFAULT_LOGGER


def find_main_executable_path(
    main_executable_path: Path, main_executable_name: str
) -> tuple[Path, Optional[Path]]:
    main_executable_path = main_executable_path.absolute().resolve()

    # check if the path is a the main executable
    if main_executable_path.is_file():
        return main_executable_path.parent, main_executable_path

    # search subdirectories for the main executable
    for path in main_executable_path.glob("**/*"):
        if path.is_file() and path.name == main_executable_name:
            return path.parent, path

    return main_executable_path, None


def launch(main_executable_path: Path, main_executable_name: str):
    directory, path = find_main_executable_path(
        main_executable_path, main_executable_name
    )

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

    args = str(path)
    DEFAULT_LOGGER.info(f"Launching RLBotServer with via {args}")

    return subprocess.Popen(args, shell=True, cwd=directory)


def find_existing_process(main_executable_name: str) -> Optional[psutil.Process]:
    logger = DEFAULT_LOGGER
    for proc in psutil.process_iter():
        try:
            if proc.name() == main_executable_name:
                return proc
        except Exception as e:
            logger.error(
                f"Failed to read the name of a process while hunting for {main_executable_name}: {e}"
            )
