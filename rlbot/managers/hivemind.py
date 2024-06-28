import os
from traceback import print_exc
from typing import Optional

from rlbot import flat
from rlbot.interface import SocketRelay
from rlbot.managers.rendering import Renderer
from rlbot.utils.logging import DEFAULT_LOGGER, get_logger


class Hivemind:
    """
    A convenience class for building a hivemind bot on top of.
    """

    _logger = DEFAULT_LOGGER
    loggers = {}

    team: int = -1
    indicies: list[int] = []
    names: list[str] = []
    spawn_ids: list[int] = []

    match_settings = flat.MatchSettings()
    field_info = flat.FieldInfo()
    ball_prediction = flat.BallPrediction()

    _initialized_bot = False
    _has_match_settings = False
    _has_field_info = False

    def __init__(self):
        spawn_ids = os.environ.get("BOT_SPAWN_IDS")

        if spawn_ids is None:
            self._logger.warning("BOT_SPAWN_IDS environment variable not set")
        else:
            spawn_ids = spawn_ids.split(",")
            self.spawn_ids = [int(spawn_id) for spawn_id in spawn_ids]
            self._logger.info(f"Spawn IDs: {self.spawn_ids}")

        self._game_interface = SocketRelay(logger=self._logger)
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

    def _handle_match_settings(self, match_settings: flat.MatchSettings):
        self.match_settings = match_settings
        self._has_match_settings = True

        # search match settings for our spawn ids
        for i, player in enumerate(self.match_settings.player_configurations):
            if player.spawn_id in self.spawn_ids:
                self.team = player.team
                self.names.append(player.name)
                self.loggers[i] = get_logger(player.name)
                break

        if not self._initialized_bot and self._has_field_info:
            self.initialize_agent()
            self._initialized_bot = True

    def _handle_field_info(self, field_info: flat.FieldInfo):
        self.field_info = field_info
        self._has_field_info = True

        if not self._initialized_bot and self._has_match_settings:
            self.initialize_agent()
            self._initialized_bot = True

    def _handle_match_communication(self, match_comm: flat.MatchComm):
        if match_comm.team_only and self.team != match_comm.team:
            return

        self.handle_match_communication(match_comm)

    def _handle_ball_prediction(self, ball_prediction: flat.BallPrediction):
        self.ball_prediction = ball_prediction

    def _handle_packet(self, packet: flat.GameTickPacket):
        if not self._initialized_bot:
            return

        if len(self.indicies) != len(self.spawn_ids):
            for i, player in enumerate(packet.players):
                if player.spawn_id in self.spawn_ids and i not in self.indicies:
                    self.indicies.append(i)
                    break

            if len(self.indicies) != len(self.spawn_ids):
                return

        try:
            controller = self.get_outputs(packet)
        except Exception as e:
            self._logger.error(
                f"Hivemind (with {self.names}) returned an error to RLBot: {e}"
            )
            print_exc()
            return

        for index, controller in controller.items():
            player_input = flat.PlayerInput(index, controller)
            self._game_interface.send_player_input(player_input)

    def run(
        self,
        wants_match_communcations: bool = True,
        wants_game_messages: bool = False,
        wants_ball_predictions: bool = True,
    ):
        try:
            self._game_interface.connect_and_run(
                wants_match_communcations,
                wants_game_messages,
                wants_ball_predictions,
            )
        finally:
            self.retire()
            del self._game_interface

    def get_match_settings(self) -> flat.MatchSettings:
        """
        Contains info about what map you're on, mutators, etc.
        """
        return self.match_settings

    def get_field_info(self) -> flat.FieldInfo:
        """
        Contains info about the map, such as the locations of boost pads and goals.
        """
        return self.field_info

    def get_ball_prediction(self) -> flat.BallPrediction:
        """
        A simulated prediction of the ball's path with only the field geometry.
        """
        return self.ball_prediction

    def handle_match_communication(self, match_comm: flat.MatchComm):
        pass

    def send_match_comm(
        self,
        index: int,
        content: bytes,
        display: Optional[str] = None,
        team_only: bool = False,
    ):
        """
        Emits a match communication

        - `content`: The other content of the communication containing arbirtrary data.
        - `display`: The message to be displayed in the game, or None to skip displaying a message.
        - `team_only`: If True, only your team will receive the communication.
        """
        self._game_interface.send_match_comm(
            flat.MatchComm(
                index,
                self.team,
                team_only,
                display,
                content,
            )
        )

    def set_game_state(self, game_state: flat.DesiredGameState):
        """
        Sets the game to the given desired state.
        """
        self._game_interface.send_game_state(game_state)

    def initialize_agent(self):
        """
        Called for all heaver initialization that needs to happen.
        Field info and match settings are fully loaded at this point, and won't return garbage data.
        """
        pass

    def retire(self):
        """Called after the game ends"""
        pass

    def get_outputs(
        self, game_tick_packet: flat.GameTickPacket
    ) -> dict[int, flat.ControllerState]:
        """
        Where all the logic of your bot gets its input and returns its output.
        """
        return {}
