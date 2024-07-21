from pathlib import Path
from time import sleep
from typing import Optional

import psutil

from rlbot import flat, version
from rlbot.interface import SocketRelay
from rlbot.utils import gateway
from rlbot.utils.logging import DEFAULT_LOGGER
from rlbot.utils.os_detector import MAIN_EXECUTABLE_NAME


class MatchManager:
    logger = DEFAULT_LOGGER
    game_state = flat.GameStateType.Inactive
    rlbot_server_process: Optional[psutil.Process] = None

    def __init__(
        self,
        main_executable_path: Optional[Path] = None,
        main_executable_name: str = MAIN_EXECUTABLE_NAME,
    ):
        self.main_executable_path = main_executable_path
        self.main_executable_name = main_executable_name

        self.rlbot_interface: SocketRelay = SocketRelay()
        self.rlbot_interface.packet_handlers.append(self._packet_reporter)

    def ensure_server_started(self, print_version_info: bool = True):
        """
        Ensures that RLBotServer is running.
        """
        if not print_version_info:
            version.print_current_release_notes()

        self.rlbot_server_process = gateway.find_existing_process(
            self.main_executable_name
        )
        if self.rlbot_server_process is not None:
            self.logger.info(f"Already have {self.main_executable_name} running!")
            return

        if self.main_executable_path is None:
            raise Exception("No main_executable_path found. Please specify it.")

        rlbot_server_process = gateway.launch(
            self.main_executable_path, self.main_executable_name
        )
        self.rlbot_server_process = psutil.Process(rlbot_server_process.pid)

        self.logger.info(
            f"Started {self.main_executable_name} with process id {self.rlbot_server_process.pid}"
        )

    def _packet_reporter(self, packet: flat.GameTickPacket):
        self.game_state = packet.game_info.game_state_type

    def wait_for_valid_packet(self):
        while self.game_state in {
            flat.GameStateType.Inactive,
            flat.GameStateType.Ended,
        }:
            sleep(0.1)

    def start_match(
        self, match_config: Path | flat.MatchSettings, wait_for_start: bool = True
    ):
        self.logger.info("Python attempting to start match.")
        self.rlbot_interface.start_match(match_config)

        if wait_for_start:
            self.wait_for_valid_packet()
            self.logger.info("Match has started.")

    def disconnect(self):
        self.rlbot_interface.disconnect()

    def shut_down(self, ensure_shutdown=True):
        self.logger.info("Shutting down RLBot...")

        # in theory this is all we need for the server to cleanly shut itself down
        try:
            self.rlbot_interface.stop_match(shutdown_server=True)
        except BrokenPipeError:
            match gateway.find_existing_process(self.main_executable_name):
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

            self.rlbot_server_process = gateway.find_existing_process(
                self.main_executable_name
            )

            if self.rlbot_server_process is not None:
                self.logger.info(
                    f"Waiting for {self.main_executable_name} to shut down..."
                )

                if ensure_shutdown:
                    if i == 1:
                        self.rlbot_server_process.terminate()
                    elif i == 4 or i == 7:
                        self.logger.warning(
                            f"{self.main_executable_name} is not responding to terminate requests."
                        )
                        self.rlbot_server_process.terminate()
                    elif i >= 10 and i % 3 == 1:
                        self.logger.error(
                            f"{self.main_executable_name} is not responding, forcefully killing."
                        )
                        self.rlbot_server_process.kill()

        self.logger.info("Shut down complete!")
