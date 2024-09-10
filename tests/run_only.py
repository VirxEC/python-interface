from pathlib import Path

from rlbot.managers import MatchManager
from rlbot.version import print_current_release_notes

CURRENT_FILE = Path(__file__).parent

MATCH_CONFIG_PATH = CURRENT_FILE / "hvn.toml"
MATCH_CONFIG_PATH = CURRENT_FILE / "rlbot.toml"

if __name__ == "__main__":
    print(print_current_release_notes())

    # start the match
    match_manager = MatchManager()
    match_manager.start_match(MATCH_CONFIG_PATH, False)

    # wait
    input("\nPress any enter to end the match: ")

    # end the match and disconnect
    match_manager.stop_match()
    match_manager.disconnect()
