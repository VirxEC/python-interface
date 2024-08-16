from pathlib import Path
from time import sleep

from rlbot import flat
from rlbot.managers import MatchManager, get_player_config
from rlbot.utils.maps import GAME_MAP_TO_UPK, STANDARD_MAPS

CURRENT_FILE = Path(__file__).parent

BOT_PATH = CURRENT_FILE / "necto/bot.toml"
RLBOT_SERVER_FOLDER = CURRENT_FILE / "../../core/RLBotCS/bin/Release/"

if __name__ == "__main__":
    match_manager = MatchManager(RLBOT_SERVER_FOLDER)
    match_manager.ensure_server_started()

    current_map = -1

    match_settings = flat.MatchSettings(
        launcher=flat.Launcher.Steam,
        auto_start_bots=True,
        game_mode=flat.GameMode.Soccer,
        enable_state_setting=True,
        existing_match_behavior=flat.ExistingMatchBehavior.Restart,
        skip_replays=True,
        player_configurations=[
            get_player_config(flat.RLBot(), 0, BOT_PATH),
            get_player_config(flat.RLBot(), 1, BOT_PATH),
        ],
    )

    while True:
        # don't use the same map
        current_map = (current_map + 1) % len(STANDARD_MAPS)
        match_settings.game_map_upk = GAME_MAP_TO_UPK[STANDARD_MAPS[current_map]]

        print(f"Starting match on {match_settings.game_map_upk}")

        match_manager.start_match(match_settings)

        while (
            match_manager.packet is None
            or match_manager.packet.game_info.game_state_type
            != flat.GameStateType.Ended
        ):
            if (
                match_manager.packet is not None
                and match_manager.packet.game_info.game_state_type
                == flat.GameStateType.Countdown
            ):
                match_manager.set_game_state(
                    flat.DesiredGameState(
                        game_info_state=flat.DesiredGameInfoState(game_speed=10)
                    )
                )

            sleep(1)

        # let the end screen play for 5 seconds (just for fun)
        sleep(5)
