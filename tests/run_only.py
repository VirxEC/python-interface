from pathlib import Path

from rlbot.managers import MatchManager

CURRENT_FILE = Path(__file__).parent

MATCH_CONFIG_PATH = CURRENT_FILE / "human_vs_atba.toml"
RLBOT_SERVER_FOLDER = CURRENT_FILE / "../../core/RLBotCS/bin/Release/"

if __name__ == "__main__":
    # start the match
    match_manager = MatchManager(RLBOT_SERVER_FOLDER)
    match_manager.start_match(MATCH_CONFIG_PATH, False)

    # wait
    input("\nPress any enter to end the match: ")

    # end the match and disconnect
    match_manager.stop_match()
    match_manager.disconnect()
