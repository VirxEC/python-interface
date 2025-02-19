import tomllib
from pathlib import Path
from typing import Any

import rlbot.flat as flat
from rlbot.utils.logging import DEFAULT_LOGGER as logger
from rlbot.utils.os_detector import CURRENT_OS, OS


class ConfigParsingException(Exception):
    pass


def __parse_enum(table: dict, key: str, enum: Any, default: int = 0) -> Any:
    if key not in table:
        return enum(default)
    try:
        for i in range(100000):
            if str(enum(i)).split('.')[-1].lower() == table[key].lower():
                return enum(i)
    except ValueError:
        raise ConfigParsingException(f"Invalid value \"{table[key]}\" for key \"{key}\".")


def load_match_config(config_path: Path | str) -> flat.MatchConfiguration:
    """
    Reads the match toml file at the provided path and creates the corresponding MatchConfiguration.
    """
    config_path = Path(config_path)
    with open(config_path, "rb") as f:
        config = tomllib.load(f)

    rlbot_table = config.get("rlbot", dict())
    match_table = config.get("match", dict())
    mutator_table = config.get("mutators", dict())

    players = []
    for car_table in config.get("cars", []):
        car_config = car_table.get("config")
        name = car_table.get("name", "")
        team = car_table.get("team", 0)
        try:
            team = int(team)
        except ValueError:
            team = {"blue": 0, "orange": 1}.get(team.lower())
        if team is None or team not in [0, 1]:
            raise ConfigParsingException(f"Invalid team \"{car_table.get("team")}\" for player {len(players)}.")

        loadout_file = car_table.get("loadout_file")
        skill = __parse_enum(car_table, "skill", flat.PsyonixSkill, int(flat.PsyonixSkill.AllStar))
        variant = car_table.get("type", "rlbot").lower()

        match variant:
            case "rlbot":
                variety, use_config = flat.CustomBot(), True
            case "psyonix":
                variety, use_config = flat.Psyonix(skill), True
            case "human":
                variety, use_config = flat.Human(), False
            case "partymember":
                logger.warning("PartyMember player type is not supported yet.")
                variety, use_config = flat.PartyMember, False
            case t:
                raise ConfigParsingException(f"Invalid player type \"{t}\" for player {len(players)}.")

        if use_config and car_config is not None:
            abs_config_path = (config_path.parent / car_config).resolve()
            players.append(load_player_config(abs_config_path, variety, team, name, loadout_file))
        else:
            loadout = load_player_loadout(loadout_file, team) if loadout_file else None
            players.append(flat.PlayerConfiguration(variety, name, team, loadout=loadout))

    scripts = []
    for script_table in config.get("scripts", []):
        if script_config := script_table.get("config"):
            abs_config_path = (config_path.parent / script_config).resolve()
            scripts.append(load_script_config(abs_config_path))
        else:
            scripts.append(flat.ScriptConfiguration())

    mutators = flat.MutatorSettings(
        match_length=__parse_enum(mutator_table, "match_length", flat.MatchLengthMutator),
        max_score=__parse_enum(mutator_table, "max_score", flat.MaxScoreMutator),
        multi_ball=__parse_enum(mutator_table, "multi_ball", flat.MultiBallMutator),
        overtime=__parse_enum(mutator_table, "overtime", flat.OvertimeMutator),
        series_length=__parse_enum(mutator_table, "series_length", flat.SeriesLengthMutator),
        game_speed=__parse_enum(mutator_table, "game_speed", flat.GameSpeedMutator),
        ball_max_speed=__parse_enum(mutator_table, "ball_max_speed", flat.BallMaxSpeedMutator),
        ball_type=__parse_enum(mutator_table, "ball_type", flat.BallTypeMutator),
        ball_weight=__parse_enum(mutator_table, "ball_weight", flat.BallWeightMutator),
        ball_size=__parse_enum(mutator_table, "ball_size", flat.BallSizeMutator),
        ball_bounciness=__parse_enum(mutator_table, "ball_bounciness", flat.BallBouncinessMutator),
        boost=__parse_enum(mutator_table, "boost_amount", flat.BoostMutator),
        rumble=__parse_enum(mutator_table, "rumble", flat.RumbleMutator),
        boost_strength=__parse_enum(mutator_table, "boost_strength", flat.BoostStrengthMutator),
        gravity=__parse_enum(mutator_table, "gravity", flat.GravityMutator),
        demolish=__parse_enum(mutator_table, "demolish", flat.DemolishMutator),
        respawn_time=__parse_enum(mutator_table, "respawn_time", flat.RespawnTimeMutator),
        max_time=__parse_enum(mutator_table, "max_time", flat.MaxTimeMutator),
        game_event=__parse_enum(mutator_table, "game_event", flat.GameEventMutator),
        audio=__parse_enum(mutator_table, "audio", flat.AudioMutator),
    )

    return flat.MatchConfiguration(
        launcher=__parse_enum(rlbot_table, "launcher", flat.Launcher),
        launcher_arg=rlbot_table.get("launcher_arg", ""),
        auto_start_bots=rlbot_table.get("auto_start_bots", True),
        game_map_upk=match_table.get("game_map_upk", ""),
        player_configurations=players,
        script_configurations=scripts,
        game_mode=__parse_enum(match_table, "game_mode", flat.GameMode),
        skip_replays=match_table.get("skip_replays", False),
        instant_start=match_table.get("instant_start", False),
        mutators=mutators,
        existing_match_behavior=__parse_enum(match_table, "existing_match_behavior", flat.ExistingMatchBehavior),
        enable_rendering=match_table.get("enable_rendering", False),
        enable_state_setting=match_table.get("enable_state_setting", False),
        freeplay=match_table.get("freeplay", False),
    )


def load_player_loadout(path: Path | str, team: int) -> flat.PlayerLoadout:
    """
    Reads the loadout toml file at the provided path and extracts the `PlayerLoadout` for the given team.
    """
    with open(path, "rb") as f:
        config = tomllib.load(f)

    loadout = config["blue_loadout"] if team == 0 else config["orange_loadout"]
    paint = None
    if paint_table := loadout.get("paint", None):
        paint = flat.LoadoutPaint(
            car_paint_id=paint_table.get("car_paint_id", 0),
            decal_paint_id=paint_table.get("decal_paint_id", 0),
            wheels_paint_id=paint_table.get("wheels_paint_id", 0),
            boost_paint_id=paint_table.get("boost_paint_id", 0),
            antenna_paint_id=paint_table.get("antenna_paint_id", 0),
            hat_paint_id=paint_table.get("hat_paint_id", 0),
            trails_paint_id=paint_table.get("trails_paint_id", 0),
            goal_explosion_paint_id=paint_table.get("goal_explosion_paint_id", 0),
        )

    return flat.PlayerLoadout(
        team_color_id=loadout.get("team_color_id", 0),
        custom_color_id=loadout.get("custom_color_id", 0),
        car_id=loadout.get("car_id", 0),
        decal_id=loadout.get("decal_id", 0),
        wheels_id=loadout.get("wheels_id", 0),
        boost_id=loadout.get("boost_id", 0),
        antenna_id=loadout.get("antenna_id", 0),
        hat_id=loadout.get("hat_id", 0),
        paint_finish_id=loadout.get("paint_finish_id", 0),
        custom_finish_id=loadout.get("custom_finish_id", 0),
        engine_audio_id=loadout.get("engine_audio_id", 0),
        trails_id=loadout.get("trails_id", 0),
        goal_explosion_id=loadout.get("goal_explosion_id", 0),
        loadout_paint=paint,
    )


def load_player_config(
    path: Path | str, type: flat.CustomBot | flat.Psyonix, team: int,
    name_override: str | None = None, loadout_override: Path | str | None = None,
) -> flat.PlayerConfiguration:
    """
    Reads the bot toml file at the provided path and
    creates a `PlayerConfiguration` of the given type for the given team.
    """
    path = Path(path)
    with open(path, "rb") as f:
        config = tomllib.load(f)

    settings: dict[str, Any] = config["settings"]

    root_dir = path.parent.absolute()
    if "root_dir" in settings:
        root_dir /= Path(settings["root_dir"])

    run_command = settings.get("run_command", "")
    if CURRENT_OS == OS.LINUX and "run_command_linux" in settings:
        run_command = settings.get("run_command_linux", "")

    loadout_path = path.parent / Path(settings["loadout_file"]) if "loadout_file" in settings else None
    loadout_path = loadout_override or loadout_path
    loadout = load_player_loadout(loadout_path, team) if loadout_path is not None else None

    return flat.PlayerConfiguration(
        type,
        name_override or settings.get("name", ""),
        team,
        str(root_dir),
        run_command,
        loadout,
        0,
        settings.get("agent_id", ""),
        settings.get("hivemind", False),
    )


def load_script_config(path: Path | str) -> flat.ScriptConfiguration:
    """
    Reads the script toml file at the provided path and creates a `ScriptConfiguration` from it.
    """
    path = Path(path)
    with open(path, "rb") as f:
        config = tomllib.load(f)

    settings: dict[str, Any] = config["settings"]

    root_dir = path.parent
    if "root_dir" in settings:
        root_dir /= Path(settings["root_dir"])

    run_command = settings.get("run_command", "")
    if CURRENT_OS == OS.LINUX and "run_command_linux" in settings:
        run_command = settings["run_command_linux"]

    return flat.ScriptConfiguration(
        settings.get("name", ""),
        str(root_dir),
        run_command,
        0,
        settings.get("agent_id", ""),
    )
