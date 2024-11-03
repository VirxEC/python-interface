from pathlib import Path
from time import sleep

from rlbot import flat
from rlbot.managers import MatchManager

CURRENT_FILE = Path(__file__).parent

MATCH_CONFIG_PATH = CURRENT_FILE / "render_test.toml"
RLBOT_SERVER_FOLDER = CURRENT_FILE / "../../core/RLBotCS/bin/Release/"

if __name__ == "__main__":
    match_manager = MatchManager(RLBOT_SERVER_FOLDER)

    match_manager.ensure_server_started()
    match_manager.start_match(MATCH_CONFIG_PATH)

    try:
        # wait for the match to end
        while match_manager.packet.game_info.game_status != flat.GameStatus.Ended:
            sleep(1.0)
    finally:
        match_manager.shut_down()
