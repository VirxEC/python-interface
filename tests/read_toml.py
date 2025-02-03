from pathlib import Path

from rlbot.config import load_match_config

DIR = Path(__file__).parent

MATCH_CONFIG_PATH = DIR / "rlbot.toml"

if __name__ == "__main__":
    print(load_match_config(MATCH_CONFIG_PATH))
