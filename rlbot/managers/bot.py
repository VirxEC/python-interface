import os
from traceback import print_exc
from typing import Optional

from rlbot import flat
from rlbot.interface import SocketRelay
from rlbot.managers.rendering import Renderer
from rlbot.utils.logging import DEFAULT_LOGGER, get_logger


class Bot:
    """
    A convenience class for building bots on top of.
    """

    logger = DEFAULT_LOGGER

    team: int = -1
    index: int = -1
    name: str = ""
    spawn_id: int = 0

    match_settings = flat.MatchSettings()
    field_info = flat.FieldInfo()
    ball_prediction = flat.BallPrediction()

    _initialized_bot = False
    _has_match_settings = False
    _has_field_info = False

    def __init__(self):
        spawn_id = os.environ.get("RLBOT_SPAWN_IDS")

        if spawn_id is None:
            self.logger.warning("RLBOT_SPAWN_IDS environment variable not set")
        else:
            self.spawn_id = int(spawn_id)
            self.logger.info("Spawn ID: %s", self.spawn_id)

        self._game_interface = SocketRelay(logger=self.logger)
        self._game_interface.match_settings_handlers.append(self._handle_match_settings)
        self._game_interface.field_info_handlers.append(self._handle_field_info)
        self._game_interface.match_communication_handlers.append(
            self.handle_match_communication
        )
        self._game_interface.ball_prediction_handlers.append(
            self._handle_ball_prediction
        )
        self._game_interface.packet_handlers.append(self._handle_packet)

        self.renderer = Renderer(self._game_interface)

    def _initialize_agent(self):
        try:
            self.initialize_agent()
        except Exception as e:
            self.logger.critical(
                "Bot %s failed to initialize due the following error: %s", self.name, e
            )
            print_exc()
            exit()

        self._initialized_bot = True
        self._game_interface.send_init_complete(flat.InitComplete(self.spawn_id))

    def _handle_match_settings(self, match_settings: flat.MatchSettings):
        self.match_settings = match_settings
        self._has_match_settings = True

        # search match settings for our spawn id
        for player in self.match_settings.player_configurations:
            if player.spawn_id == self.spawn_id:
                self.team = player.team
                self.name = player.name
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

    def _handle_packet(self, packet: flat.GameTickPacket):
        if (
            self.index == -1
            or len(packet.players) <= self.index
            or packet.players[self.index].spawn_id != self.spawn_id
        ):
            # spawn id should only be 0 if RLBOT_SPAWN_IDS was not set
            if self.spawn_id == 0:
                # in this case, if there's only one player, we can assume it's us
                player_index = -1
                for i, player in enumerate(packet.players):
                    # skip human players/psyonix bots
                    if not player.is_bot:
                        continue

                    if player_index != -1:
                        self.logger.error(
                            "Multiple bots in the game, please set RLBOT_SPAWN_IDS"
                        )
                        return

                    player_index = i
                self.index = player_index

            for i, player in enumerate(packet.players):
                if player.spawn_id == self.spawn_id:
                    self.index = i
                    break

            if self.index == -1:
                return

        try:
            controller = self.get_output(packet)
        except Exception as e:
            self.logger.error("Bot %s returned an error to RLBot: %s", self.name, e)
            print_exc()
            return

        player_input = flat.PlayerInput(self.index, controller)
        self._game_interface.send_player_input(player_input)

    def run(
        self,
        wants_match_communcations: bool = True,
        wants_ball_predictions: bool = True,
    ):
        rlbot_server_port = int(os.environ.get("RLBOT_SERVER_PORT", 23234))

        try:
            self._game_interface.connect_and_run(
                wants_match_communcations,
                wants_ball_predictions,
                rlbot_server_port=rlbot_server_port,
            )
        finally:
            self.retire()
            del self._game_interface

    def handle_match_communication(self, match_comm: flat.MatchComm):
        pass

    def send_match_comm(
        self, content: bytes, display: Optional[str] = None, team_only: bool = False
    ):
        """
        Emits a match communication

        - `content`: The other content of the communication containing arbirtrary data.
        - `display`: The message to be displayed in the game, or None to skip displaying a message.
        - `team_only`: If True, only your team will receive the communication.
        """
        self._game_interface.send_match_comm(
            flat.MatchComm(
                self.index,
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

    def set_loadout(self, loadout: flat.PlayerLoadout, spawn_id: int):
        """
        Sets the loadout of a bot.

        For use as a loadout generator, call inside of `initialize_agent`.
        Will be ignored if called outside of `initialize_agent` when state setting is disabled.
        """
        self._game_interface.send_set_loadout(flat.SetLoadout(spawn_id, loadout))

    def initialize_agent(self):
        """
        Called for all heaver initialization that needs to happen.
        Field info and match settings are fully loaded at this point, and won't return garbage data.

        NOTE: `self.index` is not set at this point, and should not be used. `self.team` and `self.name` _are_ set with correct information.
        """

    def retire(self):
        """Called after the game ends"""

    def get_output(self, game_tick_packet: flat.GameTickPacket) -> flat.ControllerState:
        """
        Where all the logic of your bot gets its input and returns its output.
        """
        raise NotImplementedError
