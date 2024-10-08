import os
from traceback import print_exc
from typing import Optional

from rlbot import flat
from rlbot.interface import SocketRelay
from rlbot.managers import Renderer
from rlbot.utils.logging import DEFAULT_LOGGER, get_logger


class Script:
    """
    A convenience class for building scripts on top of.
    """

    logger = DEFAULT_LOGGER

    index: int = 0
    name: str = "Unknown"
    spawn_id: int = 0

    match_settings = flat.MatchSettings()
    field_info = flat.FieldInfo()
    ball_prediction = flat.BallPrediction()

    _initialized_bot = False
    _has_match_settings = False
    _has_field_info = False

    def __init__(self):
        group_id = os.environ.get("RLBOT_GROUP_ID")

        if group_id is None:
            self.logger.critical("RLBOT_GROUP_ID environment variable is not set")
            exit(1)

        self._game_interface = SocketRelay(group_id, logger=self.logger)
        self._game_interface.match_settings_handlers.append(self._handle_match_settings)
        self._game_interface.field_info_handlers.append(self._handle_field_info)
        self._game_interface.match_communication_handlers.append(
            self._handle_match_communication
        )
        self._game_interface.ball_prediction_handlers.append(
            self._handle_ball_prediction
        )
        self._game_interface.packet_handlers.append(self.handle_packet)

        self.renderer = Renderer(self._game_interface)

    def _initialize_agent(self):
        try:
            self.initialize_agent()
        except Exception as e:
            self.logger.critical(
                "Script %s failed to initialize due the following error: %s",
                self.name,
                e,
            )
            print_exc()
            exit()

        self._initialized_bot = True
        self._game_interface.send_init_complete()

    def _handle_match_settings(self, match_settings: flat.MatchSettings):
        self.match_settings = match_settings
        self._has_match_settings = True

        # search match settings for our spawn id
        for script in self.match_settings.script_configurations:
            if script.spawn_id == self.spawn_id or self.spawn_id == 0:
                self.name = script.name
                self.logger = get_logger(self.name)
                break

        if not self._initialized_bot and self._has_field_info:
            self._initialize_agent()

    def _handle_field_info(self, field_info: flat.FieldInfo):
        self.field_info = field_info
        self._has_field_info = True

        if not self._initialized_bot and self._has_match_settings:
            self._initialize_agent()

    def _handle_ball_prediction(self, ball_prediction: flat.BallPrediction):
        self.ball_prediction = ball_prediction

    def run(
        self,
        wants_match_communications: bool = True,
        wants_ball_predictions: bool = True,
    ):
        rlbot_server_port = int(os.environ.get("RLBOT_SERVER_PORT", 23234))

        try:
            self._game_interface.connect_and_run(
                wants_match_communications,
                wants_ball_predictions,
                rlbot_server_port=rlbot_server_port,
            )
        finally:
            self.retire()
            del self._game_interface

    def _handle_match_communication(self, match_comm: flat.MatchComm):
        self.handle_match_communication(
            match_comm.index,
            match_comm.team,
            match_comm.content,
            match_comm.display,
            match_comm.team_only,
        )

    def handle_match_communication(
        self,
        index: int,
        team: int,
        content: bytes,
        display: Optional[str],
        team_only: bool,
    ):
        """
        Called when a match communication is received.
        """

    def send_match_comm(
        self, content: bytes, display: Optional[str] = None, team_only: bool = False
    ):
        """
        Emits a match communication; WARNING: as a script, you will recieve your own communication after you send it.

        - `content`: The other content of the communication containing arbirtrary data.
        - `display`: The message to be displayed in the game, or None to skip displaying a message.
        - `scripts_only`: If True, only other scripts will receive the communication.
        """
        self._game_interface.send_match_comm(
            flat.MatchComm(
                self.index,
                2,
                team_only,
                display,
                content,
            )
        )

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

        self._game_interface.send_game_state(game_state)

    def set_loadout(self, loadout: flat.PlayerLoadout, spawn_id: int):
        """
        Sets the loadout of a bot.

        Will be ignored if called when state setting is disabled.
        """
        self._game_interface.send_set_loadout(flat.SetLoadout(self.spawn_id, loadout))

    def initialize_agent(self):
        """
        Called for all heaver initialization that needs to happen.
        Field info and match settings are fully loaded at this point, and won't return garbage data.
        """

    def retire(self):
        """Called after the game ends"""

    def handle_packet(self, packet: flat.GameTickPacket):
        pass
