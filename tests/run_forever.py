from pathlib import Path
from time import sleep

from rlbot import flat
from rlbot.managers import MatchManager, get_player_config
from rlbot.utils.maps import GAME_MAP_TO_UPK, STANDARD_MAPS

THIS_DIR = Path(__file__).parent

BOT_PATH = THIS_DIR / "atba/atba.bot.toml"
RLBOT_SERVER_FOLDER = THIS_DIR / "../../core/RLBotCS/bin/Release/"

if __name__ == "__main__":
    match_manager = MatchManager(RLBOT_SERVER_FOLDER)
    match_manager.ensure_server_started()

    current_map = -1

    blue_bot = get_player_config(flat.CustomBot(), 0, BOT_PATH)
    orange_bot = get_player_config(flat.CustomBot(), 1, BOT_PATH)

    match_settings = flat.MatchConfiguration(
        launcher=flat.Launcher.Steam,
        auto_start_bots=True,
        game_mode=flat.GameMode.Soccer,
        enable_state_setting=True,
        existing_match_behavior=flat.ExistingMatchBehavior.Restart,
        skip_replays=True,
        mutators=flat.MutatorSettings(
            match_length=flat.MatchLengthMutator.FiveMinutes,
        ),
        player_configurations=[
            blue_bot,
            blue_bot,
            blue_bot,
            orange_bot,
            orange_bot,
            orange_bot,
        ],
    )

    while True:
        # don't use the same map
        current_map = (current_map + 1) % len(STANDARD_MAPS)
        match_settings.game_map_upk = GAME_MAP_TO_UPK[STANDARD_MAPS[current_map]]

        print(f"Starting match on {match_settings.game_map_upk}")

        match_manager.start_match(match_settings)
        # when calling start_match, by default it will wait for the first packet
        assert match_manager.packet is not None

        while match_manager.packet.match_info.match_phase != flat.MatchPhase.Ended:
            if match_manager.packet.match_info.match_phase == flat.MatchPhase.Countdown:
                match_manager.set_game_state(
                    match_info=flat.DesiredMatchInfo(game_speed=2)
                )

            sleep(1)

        # let the end screen play for 5 seconds (just for fun)
        sleep(5)
