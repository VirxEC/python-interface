from configparser import RawConfigParser
from pathlib import Path
from typing import Any

import toml


def cfg_to_dict(path: Path) -> dict[str, dict[str, str]]:
    config = RawConfigParser()
    config.read(path)

    dict_config: dict[str, dict[str, str]] = {}
    for section in config.sections():
        dict_config[section] = {}
        for key, value in config.items(section):
            dict_config[section][key] = value

    return dict_config


def write_to_toml(path: Path, config: dict[str, dict[str, Any]]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        toml.dump(config, f)


class Loadout:
    def __init__(self, path: Path):
        self.cfg_dict = cfg_to_dict(path)

    def _convert_dict_section(self, old_name: str) -> dict[str, int]:
        return {
            key: int(value)
            for key, value in self.cfg_dict[old_name].items()
            if key not in {"primary_color_lookup", "secondary_color_lookup"}
        }

    def convert_to_toml(self) -> dict[str, dict[str, Any]]:
        toml_dict: dict[str, dict[str, Any]] = {}

        for section in self.cfg_dict.keys():
            if section == "Bot Loadout":
                toml_dict["blue_loadout"] = self._convert_dict_section(section)
            elif section == "Bot Loadout Orange":
                toml_dict["orange_loadout"] = self._convert_dict_section(section)
            elif section == "Bot Paint Blue":
                toml_dict["blue_loadout"]["paint"] = self._convert_dict_section(section)  # type: ignore
            elif section == "Bot Paint Orange":
                toml_dict["orange_loadout"]["paint"] = self._convert_dict_section(  # type: ignore
                    section
                )

        return toml_dict

    def write_to_toml(self, path: Path):
        write_to_toml(path, self.convert_to_toml())


class Bot:
    def __init__(self, path: Path):
        self.parent_path = path.parent
        self.cfg_dict = cfg_to_dict(path)

    def _convert_settings(self) -> dict[str, str]:
        settings: dict[str, str] = {}

        use_virtual_environment = False
        python_file = ""

        for key, value in self.cfg_dict["Locations"].items():
            if key == "looks_config":
                key = "loadout_file"
                value = value.replace(".cfg", ".toml")
            elif key == "use_virtual_environment":
                use_virtual_environment = True
                continue
            elif key == "maximum_tick_rate_preference":
                assert int(value) == 120, "Only 120 tick rate is supported"
                continue
            elif key == "python_file":
                python_file = value
                continue
            elif key in {
                "requirements_file",
                "supports_early_start",
                "supports_standalone",
            }:
                continue
            settings[key] = value

        if use_virtual_environment:
            settings["run_command"] = ".\\venv\\Scripts\\python " + python_file
            settings["run_command_linux"] = "./venv/bin/python " + python_file
        else:
            settings["run_command"] = "python " + python_file
            settings["run_command_linux"] = "python3 " + python_file

        return settings

    def _convert_details(self) -> dict[str, str | list[str]]:
        details: dict[str, str | list[str]] = {}

        for key, value in self.cfg_dict["Details"].items():
            if key == "tags":
                details[key] = [tag.strip() for tag in value.split(",")]
                continue
            details[key] = value

        return details

    def convert_to_toml(self) -> dict[str, dict[str, Any]]:
        toml_dict: dict[str, dict[str, Any]] = {}

        toml_dict["settings"] = self._convert_settings()
        toml_dict["details"] = self._convert_details()
        toml_dict["settings"][
            "agent_id"
        ] = f"{toml_dict["details"]["developer"]}/{toml_dict["settings"]["name"]}"

        return toml_dict

    def write_to_toml(self, bot_path: Path):
        config = self.convert_to_toml()
        write_to_toml(bot_path, config)

        old_loadout = config["settings"]["loadout_file"]
        Loadout(self.parent_path / old_loadout.replace(".toml", ".cfg")).write_to_toml(
            bot_path.parent / old_loadout
        )


if __name__ == "__main__":
    import sys

    in_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

    bot = Bot(in_path)
    bot.write_to_toml(out_path)

    print(f"Converted {in_path} to {out_path}")
