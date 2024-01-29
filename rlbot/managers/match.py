from pathlib import Path
from time import sleep
from typing import Optional

import psutil
import rlbot_flatbuffers as flat

from rlbot import version
from rlbot.interface import SocketRelay
from rlbot.utils import gateway
from rlbot.utils.logging import DEFAULT_LOGGER
from rlbot.utils.os_detector import MAIN_EXECUTABLE_NAME


class MatchManager:
    def __init__(self, main_executable_path: Optional[Path] = None):
        self.main_executable_path = main_executable_path

        self.logger = DEFAULT_LOGGER
        self.game_state = int(flat.GameStateType.Inactive)
        self.rlbot_server_process: Optional[psutil.Process] = None

        self.rlbot_interface: SocketRelay = SocketRelay()
        self.rlbot_interface.packet_handlers.append(self.packet_reporter)

    def ensure_server_started(self) -> int:
        """
        Ensures that RLBotServer is running.

        Returns the port that it will be listening on for connections from Rocket League.
        Rocket League should be passed a command line argument so that it starts with this same port.
        """

        self.rlbot_server_process, port = gateway.find_existing_process()
        if self.rlbot_server_process is not None:
            self.logger.info(
                f"Already have {MAIN_EXECUTABLE_NAME} running! Port is {port}"
            )
            return port

        if self.main_executable_path is None:
            raise Exception("No main_executable_path found. Please specify it.")

        rlbot_server_process, port = gateway.launch(self.main_executable_path)
        self.rlbot_server_process = psutil.Process(rlbot_server_process.pid)

        self.logger.info(
            f"Started {MAIN_EXECUTABLE_NAME} with process id {self.rlbot_server_process.pid} "
            f"and port {port}"
        )

        return port

    def connect_to_game(self):
        """
        Connects to the game by initializing self.game_interface.
        """
        version.print_current_release_notes()

        port = self.ensure_server_started()
        self.logger.info(f"Connecting to game on port {port}...")

    def packet_reporter(self, packet: flat.GameTickPacket):
        self.game_state = int(packet.game_info.game_state_type)

    def wait_for_valid_packet(self):
        while self.game_state in {
            int(flat.GameStateType.Inactive),
            int(flat.GameStateType.Ended),
        }:
            print(self.game_state)
            sleep(0.1)
        print(self.game_state)

    def start_match(self, match_config_path: Path):
        self.logger.info("Python attempting to start match.")
        self.rlbot_interface.start_match(match_config_path)

        self.wait_for_valid_packet()
        self.logger.info("Match has started.")

    def shut_down(self):
        self.logger.info("Shutting down RLBot...")

        self.rlbot_interface.disconnect()

        if self.rlbot_server_process is None:
            self.logger.warning(f"{MAIN_EXECUTABLE_NAME} is not running.")
            return
        
        self.logger.info(f"Killing {MAIN_EXECUTABLE_NAME}...")
        self.rlbot_server_process.terminate()

        # often the process doesn't die on the first try
        # so we wait a second and try again (this usually works fine)
        # if we end up waiting more than 4 seconds, we start spitting out warnings
        # if we have to wait more than 10 seconds, spit out a warning and start calling kill

        i = 0
        while self.rlbot_server_process is not None:
            i += 1
            sleep(1)

            self.rlbot_server_process, _ = gateway.find_existing_process()

            if self.rlbot_server_process is not None:
                if i == 1:
                    self.rlbot_server_process.terminate()
                elif i == 4 or i == 7:
                    self.logger.warning(
                        f"{MAIN_EXECUTABLE_NAME} is not responding to terminate requests."
                    )
                    self.rlbot_server_process.terminate()
                elif i >= 10 and i % 3 == 1:
                    self.logger.error(
                        f"{MAIN_EXECUTABLE_NAME} is not responding, forcefully killing."
                    )
                    self.rlbot_server_process.kill()

        self.logger.info("Shut down complete!")
