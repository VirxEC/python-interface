from pathlib import Path
from time import sleep

from rlbot import flat
from rlbot.managers import MatchManager

CURRENT_FILE = Path(__file__).parent

MATCH_CONFIG_PATH = CURRENT_FILE / "series.toml"
RLBOT_SERVER_FOLDER = CURRENT_FILE / "../../core/RLBotCS/bin/Release/"

if __name__ == "__main__":
    match_manager = MatchManager(RLBOT_SERVER_FOLDER)
    match_manager.ensure_server_started()

    while True:
        match_manager.start_match(MATCH_CONFIG_PATH)

        while (
            match_manager.packet is None
            or match_manager.packet.game_info.game_state_type
            != flat.GameStateType.Ended
        ):
            if (
                match_manager.packet is not None
                and match_manager.packet.game_info.game_state_type
                == flat.GameStateType.Active
            ):
                match_manager.rlbot_interface.send_game_state(
                    flat.DesiredGameState(
                        game_info_state=flat.DesiredGameInfoState(game_speed=5)
                    )
                )

            sleep(0.1)

        # let the end screen play for 5 seconds
        sleep(5)
