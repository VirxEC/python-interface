from pathlib import Path
from time import sleep
from typing import Optional

import psutil

from rlbot import flat
from rlbot.interface import RLBOT_SERVER_IP, RLBOT_SERVER_PORT, SocketRelay
from rlbot.utils import fill_desired_game_state, gateway
from rlbot.utils.logging import DEFAULT_LOGGER
from rlbot.utils.os_detector import MAIN_EXECUTABLE_NAME


class MatchManager:
    """
    A simple match manager to start and stop matches.
    """

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

    def ensure_server_started(self):
        """
        Ensures that RLBotServer is running, starting it if it is not.
        """

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

    def connect(
        self,
        *,
        wants_match_communications: bool,
        wants_ball_predictions: bool,
        close_between_matches: bool = True,
        rlbot_server_ip: str = RLBOT_SERVER_IP,
        rlbot_server_port: int = RLBOT_SERVER_PORT,
    ):
        """
        Connects to the RLBot server specifying the given settings.

        - wants_match_communications: Whether match communication messages should be sent to this process.
        - wants_ball_predictions: Whether ball prediction messages should be sent to this process.
        - close_between_matches: Whether RLBot should close this connection between matches, specifically upon
            `StartMatch` and `StopMatch` messages, since RLBot does not actually detect the ending of matches.
        """
        self.rlbot_interface.connect(
            wants_match_communications=wants_match_communications,
            wants_ball_predictions=wants_ball_predictions,
            close_between_matches=close_between_matches,
            rlbot_server_ip=rlbot_server_ip,
            rlbot_server_port=rlbot_server_port,
        )

    def wait_for_first_packet(self):
        while self.packet is None or self.packet.match_info.match_phase in {
            flat.MatchPhase.Inactive,
            flat.MatchPhase.Ended,
        }:
            sleep(0.1)

    def start_match(
        self, config: Path | flat.MatchConfiguration, wait_for_start: bool = True
    ):
        """
        Starts a match using the given match settings or a path to a match settings toml file.
        Connection is automatically established if missing. Call `connect` if you
        want this process to receive match communication or ball prediction messages.
        """

        self.ensure_server_started()

        if not self.rlbot_interface.is_connected:
            self.rlbot_interface.connect(
                wants_match_communications=False,
                wants_ball_predictions=False,
                close_between_matches=False,
            )
            self.rlbot_interface.run(background_thread=True)

        self.rlbot_interface.start_match(config)

        if not self.initialized:
            self.rlbot_interface.send_init_complete()
            self.initialized = True

        if wait_for_start:
            self.wait_for_first_packet()
            self.logger.debug("First packet received")

    def disconnect(self):
        """
        Disconnect from the RLBotServer.
        Note that the server will continue running as long as Rocket League does.
        """
        self.rlbot_interface.disconnect()

    def stop_match(self):
        self.rlbot_interface.stop_match()

    def set_game_state(
        self,
        balls: dict[int, flat.DesiredBallState] = {},
        cars: dict[int, flat.DesiredCarState] = {},
        match_info: Optional[flat.DesiredMatchInfo] = None,
        commands: list[str] = [],
    ):
        """
        Sets the game to the desired state.
        Through this it is possible to manipulate the position, velocity, and rotations of cars and balls, and more.
        See wiki for a full break down and examples.
        """

        game_state = fill_desired_game_state(balls, cars, match_info, commands)
        self.rlbot_interface.send_game_state(game_state)

    def shut_down(self, use_force_if_necessary: bool = True):
        """
        Shutdown the RLBotServer process.
        """

        self.logger.info("Shutting down RLBot...")

        # In theory this is all we need for the server to cleanly shut itself down
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

        # Wait for the server to shut down.
        # It usually happens quickly, but if it doesn't,
        # we'll forcefully kill it after a few seconds.

        sleeps = 0
        while self.rlbot_server_process is not None:
            sleeps += 1
            sleep(1)

            self.rlbot_server_process, _ = gateway.find_server_process(
                self.main_executable_name
            )

            if self.rlbot_server_process is not None:
                self.logger.info(
                    "Waiting for %s to shut down...", self.main_executable_name
                )

                if use_force_if_necessary:
                    if sleeps == 1:
                        self.rlbot_server_process.terminate()
                    elif sleeps == 4 or sleeps == 7:
                        self.logger.warning(
                            "%s is not responding to terminate requests.",
                            self.main_executable_name,
                        )
                        self.rlbot_server_process.terminate()
                    elif sleeps >= 10 and sleeps % 3 == 1:
                        self.logger.error(
                            "%s is not responding, forcefully killing.",
                            self.main_executable_name,
                        )
                        self.rlbot_server_process.kill()

        self.logger.info("Shut down complete!")
