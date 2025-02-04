from pathlib import Path
from time import sleep
from traceback import print_exc

from rlbot.managers.match import MatchManager
from rlbot.utils.logging import get_logger

DIR = Path(__file__).parent

MATCH_CONFIG_PATH = DIR / "human_vs_atba.toml"
RLBOT_SERVER_FOLDER = DIR / "../../core/RLBotCS/bin/Release/"

if __name__ == "__main__":
    logger = get_logger("runner")

    match_manager = MatchManager(RLBOT_SERVER_FOLDER)

    try:
        match_manager.ensure_server_started()
        match_manager.start_match(MATCH_CONFIG_PATH)

        logger.info("Waiting before shutdown...")
        sleep(10)
        raise Exception("Test exception")
    except KeyboardInterrupt:
        logger.warning("Shutting down early due to interrupt")
    except Exception:
        logger.critical(f"Shutting down early due to the following error:")
        print_exc()

    match_manager.shut_down()
