from pathlib import Path

from rlbot import flat
from rlbot.managers.match import get_player_config

CURRENT_FILE = Path(__file__).parent

if __name__ == "__main__":
    print(get_player_config(flat.CustomBot(), 0, CURRENT_FILE / "necto/bot.toml"))
