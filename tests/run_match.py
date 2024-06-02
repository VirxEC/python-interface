from pathlib import Path
from time import sleep

from rlbot import flat
from rlbot.managers.match import MatchManager
from rlbot.utils.os_detector import MAIN_EXECUTABLE_NAME

CURRENT_FILE = Path(__file__).parent

MATCH_CONFIG_PATH = CURRENT_FILE / "hvn.toml"
RLBOT_SERVER_FOLDER = CURRENT_FILE / "../../core/RLBotCS/bin/Release/"

if __name__ == "__main__":
    match_manager = MatchManager(RLBOT_SERVER_FOLDER, MAIN_EXECUTABLE_NAME)

    match_manager.connect_to_game()
    match_manager.start_match(MATCH_CONFIG_PATH)

    sleep(5)

    while match_manager.game_state != flat.GameStateType.Ended:
        sleep(0.1)

    match_manager.shut_down()
