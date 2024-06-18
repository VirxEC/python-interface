from pathlib import Path
from time import sleep
from traceback import print_exc

from rlbot.managers.match import MatchManager
from rlbot.utils.logging import get_logger
from rlbot.utils.os_detector import OS, CURRENT_OS, MAIN_EXECUTABLE_NAME

CURRENT_FILE = Path(__file__).parent

MATCH_CONFIG_PATH = CURRENT_FILE / "rlbot.toml"

SIMULATION = False

if SIMULATION:
    RLBOT_SERVER_FOLDER = None

    if CURRENT_OS == OS.WINDOWS:
        MAIN_EXECUTABLE_NAME = "rlbot_server_sim.exe"
    elif CURRENT_OS == OS.LINUX:
        MAIN_EXECUTABLE_NAME = "rlbot_server_sim"
else:
    RLBOT_SERVER_FOLDER = CURRENT_FILE / "../../core/RLBotCS/bin/Release/"

if __name__ == "__main__":
    logger = get_logger("runner")

    match_manager = MatchManager(RLBOT_SERVER_FOLDER, MAIN_EXECUTABLE_NAME)

    try:
        match_manager.connect_to_game()
        match_manager.start_match(MATCH_CONFIG_PATH)

        logger.info("Waiting before shutdown...")
        sleep(360)
        raise Exception("Test exception")
    except KeyboardInterrupt:
        logger.warning("Shutting down early due to interrupt")
    except Exception:
        logger.critical(f"Shutting down early due to the following error:")
        print_exc()

    match_manager.shut_down()
