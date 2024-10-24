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
    agent_id: str = None

    match_settings = flat.MatchSettings()
    field_info = flat.FieldInfo()
    ball_prediction = flat.BallPrediction()

    _initialized_script = False
    _has_match_settings = False
    _has_field_info = False

    _latest_packet: Optional[flat.GamePacket] = None
    _latest_prediction = flat.BallPrediction()

    def __init__(self, default_agent_id: Optional[str] = None):
        agent_id = os.environ.get("RLBOT_AGENT_ID") or default_agent_id

        if agent_id is None:
            self.logger.critical("RLBOT_AGENT_ID environment variable is not set")
            exit(1)

        self._game_interface = SocketRelay(agent_id, logger=self.logger)
        self._game_interface.match_settings_handlers.append(self._handle_match_settings)
        self._game_interface.field_info_handlers.append(self._handle_field_info)
        self._game_interface.match_communication_handlers.append(
            self._handle_match_communication
        )
        self._game_interface.ball_prediction_handlers.append(
            self._handle_ball_prediction
        )
        self._game_interface.packet_handlers.append(self._handle_packet)

        self.renderer = Renderer(self._game_interface)

    def _try_initialize(self):
        if self._initialized_script or not self._has_match_settings:
            return

        self.logger = get_logger(self.name)

        try:
            self.initialize()
        except Exception as e:
            self.logger.critical(
                "Script %s failed to initialize due the following error: %s",
                self.name,
                e,
            )
            print_exc()
            exit()

        self._initialized_script = True
        self._game_interface.send_init_complete()

    def _handle_match_settings(self, match_settings: flat.MatchSettings):
        self.match_settings = match_settings

        for i, script in enumerate(match_settings.script_configurations):
            if script.agent_id == self.agent_id:
                self.index = i
                self.name = script.name
                self._has_match_settings = True
                break
        else:   # else block runs if break was not hit
            self.logger.warning("Script with agent id '%s' did not find itself in the match settings", self.agent_id)

        self._try_initialize()

    def _handle_field_info(self, field_info: flat.FieldInfo):
        self.field_info = field_info
        self._has_field_info = True
        self._try_initialize()

    def _handle_ball_prediction(self, ball_prediction: flat.BallPrediction):
        self._latest_prediction = ball_prediction

    def _handle_packet(self, packet: flat.GamePacket):
        self._latest_packet = packet

    def _packet_processor(self, packet: flat.GamePacket):

        self.ball_prediction = self._latest_prediction

        try:
            self.handle_packet(packet)
        except Exception as e:
            self.logger.error("Script %s returned an error to RLBot: %s", self.name, e)
            print_exc()

    def run(
        self,
        wants_match_communications: bool = True,
        wants_ball_predictions: bool = True,
    ):
        rlbot_server_port = int(os.environ.get("RLBOT_SERVER_PORT", 23234))

        try:
            self._game_interface.connect(
                wants_match_communications,
                wants_ball_predictions,
                rlbot_server_port=rlbot_server_port,
            )

            # see bot.py for an explanation of this loop
            while True:
                try:
                    self._game_interface.handle_incoming_messages(True)
                    break
                except BlockingIOError:
                    pass

                if self._latest_packet is None:
                    self._game_interface.socket.setblocking(True)
                    continue

                self._packet_processor(self._latest_packet)
                self._latest_packet = None
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

    def initialize(self):
        """
        Called for all heaver initialization that needs to happen.
        Field info and match settings are fully loaded at this point, and won't return garbage data.
        """

    def retire(self):
        """Called after the game ends"""

    def handle_packet(self, packet: flat.GamePacket):
        pass
