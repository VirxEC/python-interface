from pathlib import Path
from time import sleep

from rlbot import flat
from rlbot.managers import MatchManager

DIR = Path(__file__).parent

MATCH_CONFIG_PATH = DIR / "render_test.toml"
RLBOT_SERVER_FOLDER = DIR / "../../core/RLBotCS/bin/Release/"

if __name__ == "__main__":
    match_manager = MatchManager(RLBOT_SERVER_FOLDER)

    match_manager.ensure_server_started()
    match_manager.start_match(MATCH_CONFIG_PATH)
    assert match_manager.packet is not None

    try:
        # wait for the match to end
        while match_manager.packet.match_info.match_phase != flat.MatchPhase.Ended:
            sleep(1.0)
    finally:
        match_manager.shut_down()
