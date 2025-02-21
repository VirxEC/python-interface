import sys
from pathlib import Path

from rlbot.managers import MatchManager

DIR = Path(__file__).parent

MATCH_CONFIG_PATH = DIR / "human_vs_necto.toml"
RLBOT_SERVER_FOLDER = DIR / "../"

if __name__ == "__main__":
    match_config_path = MATCH_CONFIG_PATH
    if len(sys.argv) > 1:
        match_config_path = Path(sys.argv[1])
    assert match_config_path.exists(), f"Match config not found: {match_config_path}"

    # start the match
    match_manager = MatchManager(RLBOT_SERVER_FOLDER)
    match_manager.start_match(match_config_path, False)

    # wait
    input("\nPress enter to end the match: ")

    # end the match and disconnect
    match_manager.stop_match()
    match_manager.disconnect()
