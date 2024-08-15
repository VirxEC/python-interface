from pathlib import Path

from rlbot.managers import MatchManager

CURRENT_FILE = Path(__file__).parent

MATCH_CONFIG_PATH = CURRENT_FILE / "hvn.toml"

if __name__ == "__main__":
    match_manager = MatchManager()
    match_manager.start_match(MATCH_CONFIG_PATH, False)
    input()
    match_manager.stop_match()
    match_manager.disconnect()
