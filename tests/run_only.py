from pathlib import Path

from rlbot.managers import MatchManager

DIR = Path(__file__).parent

MATCH_CONFIG_PATH = DIR / "human_vs_necto.toml"
RLBOT_SERVER_FOLDER = DIR / "../"

if __name__ == "__main__":
    # start the match
    match_manager = MatchManager(RLBOT_SERVER_FOLDER)
    match_manager.start_match(MATCH_CONFIG_PATH, False)

    # wait
    input("\nPress enter to end the match: ")

    # end the match and disconnect
    match_manager.stop_match()
    match_manager.disconnect()
