import tomllib
from pathlib import Path
from time import sleep
from typing import Any, Optional

import psutil

from rlbot import flat, version
from rlbot.interface import RLBOT_SERVER_PORT, SocketRelay
from rlbot.utils import gateway
from rlbot.utils.logging import DEFAULT_LOGGER
from rlbot.utils.os_detector import CURRENT_OS, MAIN_EXECUTABLE_NAME, OS


def get_player_paint(config: dict[str, Any]) -> flat.LoadoutPaint:
    return flat.LoadoutPaint(
        config.get("car_paint_id", 0),
        config.get("decal_paint_id", 0),
        config.get("wheels_paint_id", 0),
        config.get("boost_paint_id", 0),
        config.get("antenna_paint_id", 0),
        config.get("hat_paint_id", 0),
        config.get("trails_paint_id", 0),
        config.get("goal_explosion_paint_id", 0),
    )


def get_player_loadout(path: str, team: int) -> flat.PlayerLoadout:
    with open(path, "rb") as f:
        config = tomllib.load(f)

    loadout = config["blue_loadout"] if team == 0 else config["orange_loadout"]
    paint = loadout.get("paint", None)

    return flat.PlayerLoadout(
        loadout.get("team_color_id", 0),
        loadout.get("custom_color_id", 0),
        loadout.get("car_id", 0),
        loadout.get("decal_id", 0),
        loadout.get("wheels_id", 0),
        loadout.get("boost_id", 0),
        loadout.get("antenna_id", 0),
        loadout.get("hat_id", 0),
        loadout.get("paint_finish_id", 0),
        loadout.get("custom_finish_id", 0),
        loadout.get("engine_audio_id", 0),
        loadout.get("trails_id", 0),
        loadout.get("goal_explosion_id", 0),
        get_player_paint(paint) if paint is not None else None,
    )


def get_player_config(
    type: flat.RLBot | flat.Psyonix, team: int, path: Path | str
) -> flat.PlayerConfiguration:
    with open(path, "rb") as f:
        config = tomllib.load(f)

    match path:
        case Path():
            parent = path.parent
        case _:
            parent = Path(path).parent

    settings: dict[str, Any] = config["settings"]

    location = parent
    if "location" in settings:
        location /= settings["location"]

    run_command = settings.get("run_command", "")
    if CURRENT_OS == OS.LINUX and "run_command_linux" in settings:
        run_command = settings["run_command_linux"]

    loadout_path = settings.get("loadout_file", None)
    if loadout_path is not None:
        loadout_path = parent / loadout_path

    loadout = (
        get_player_loadout(loadout_path, team)
        if loadout_path is not None and loadout_path.exists()
        else None
    )

    return flat.PlayerConfiguration(
        type,
        settings["name"],
        team,
        str(location),
        str(run_command),
        loadout,
        0,
        settings.get("group_id", ""),
        settings.get("hivemind", False),
    )


class MatchManager:
    logger = DEFAULT_LOGGER
    packet: Optional[flat.GamePacket] = None
    rlbot_server_process: Optional[psutil.Process] = None
    rlbot_server_port = RLBOT_SERVER_PORT
    initialized = False

    def __init__(
        self,
        main_executable_path: Optional[Path] = None,
        main_executable_name: str = MAIN_EXECUTABLE_NAME,
    ):
        self.main_executable_path = main_executable_path
        self.main_executable_name = main_executable_name

        self.rlbot_interface: SocketRelay = SocketRelay("")
        self.rlbot_interface.packet_handlers.append(self._packet_reporter)

    def ensure_server_started(self, print_version_info: bool = True):
        """
        Ensures that RLBotServer is running.
        """
        if print_version_info:
            version.print_current_release_notes()

        self.rlbot_server_process, self.rlbot_server_port = gateway.find_server_process(
            self.main_executable_name
        )
        if self.rlbot_server_process is not None:
            self.logger.info("Already have %s running!", self.main_executable_name)
            return

        if self.main_executable_path is None:
            self.main_executable_path = Path.cwd()

        rlbot_server_process, self.rlbot_server_port = gateway.launch(
            self.main_executable_path,
            self.main_executable_name,
        )
        self.rlbot_server_process = psutil.Process(rlbot_server_process.pid)

        self.logger.info(
            "Started %s with process id %s",
            self.main_executable_name,
            self.rlbot_server_process.pid,
        )

    def _packet_reporter(self, packet: flat.GamePacket):
        self.packet = packet

    def wait_for_valid_packet(self):
        while self.packet is not None and self.packet.game_info.game_status in {
            flat.GameStatus.Inactive,
            flat.GameStatus.Ended,
        }:
            sleep(0.1)

    def start_match(
        self, match_config: Path | flat.MatchSettings, wait_for_start: bool = True
    ):
        self.logger.info("Python attempting to start match.")
        self.rlbot_interface.start_match(match_config, self.rlbot_server_port)

        if not self.initialized:
            self.rlbot_interface.send_init_complete()
            self.initialized = True

        if wait_for_start:
            self.wait_for_valid_packet()
            self.logger.info("Match has started.")

    def disconnect(self):
        self.rlbot_interface.disconnect()

    def stop_match(self):
        self.rlbot_interface.stop_match()

    def set_game_state(
        self,
        balls: dict[int, flat.DesiredBallState] = {},
        cars: dict[int, flat.DesiredCarState] = {},
        game_info: Optional[flat.DesiredGameInfoState] = None,
        commands: list[flat.ConsoleCommand] = [],
    ):
        """
        Sets the game to the desired state.
        """

        game_state = flat.DesiredGameState(
            game_info_state=game_info, console_commands=commands
        )

        # convert the dictionaries to lists by
        # filling in the blanks with empty states

        if balls:
            max_entry = max(balls.keys())
            game_state.ball_states = [
                balls.get(i, flat.DesiredBallState()) for i in range(max_entry + 1)
            ]

        if cars:
            max_entry = max(cars.keys())
            game_state.car_states = [
                cars.get(i, flat.DesiredCarState()) for i in range(max_entry + 1)
            ]

        self.rlbot_interface.send_game_state(game_state)

    def shut_down(self, ensure_shutdown=True):
        self.logger.info("Shutting down RLBot...")

        # in theory this is all we need for the server to cleanly shut itself down
        try:
            self.rlbot_interface.stop_match(shutdown_server=True)
        except BrokenPipeError:
            match gateway.find_server_process(self.main_executable_name)[0]:
                case psutil.Process() as proc:
                    self.logger.warning(
                        "Can't communicate with RLBotServer, ensuring shutdown."
                    )
                    proc.terminate()
                case None:
                    self.logger.warning(
                        "RLBotServer appears to have already shut down."
                    )
                    return

        # Wait for the server to shut down
        # It usually happens quickly, but if it doesn't,
        # we'll forcefully kill it after a few seconds.

        i = 0
        while self.rlbot_server_process is not None:
            i += 1
            sleep(1)

            self.rlbot_server_process, _ = gateway.find_server_process(
                self.main_executable_name
            )

            if self.rlbot_server_process is not None:
                self.logger.info(
                    "Waiting for %s to shut down...", self.main_executable_name
                )

                if ensure_shutdown:
                    if i == 1:
                        self.rlbot_server_process.terminate()
                    elif i == 4 or i == 7:
                        self.logger.warning(
                            "%s is not responding to terminate requests.",
                            self.main_executable_name,
                        )
                        self.rlbot_server_process.terminate()
                    elif i >= 10 and i % 3 == 1:
                        self.logger.error(
                            "%s is not responding, forcefully killing.",
                            self.main_executable_name,
                        )
                        self.rlbot_server_process.kill()

        self.logger.info("Shut down complete!")
