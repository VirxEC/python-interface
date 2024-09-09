import os
from threading import Event, Thread
from traceback import print_exc
from typing import Optional

from rlbot import flat
from rlbot.interface import SocketRelay
from rlbot.managers import Renderer
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

    _latest_packet = flat.GameTickPacket()
    _lastest_prediction = flat.BallPrediction()
    _packet_event = Event()
    _packet_thread = None
    _run_packet_thread = True

    def __init__(self):
        spawn_ids = os.environ.get("RLBOT_SPAWN_IDS")

        if spawn_ids is None:
            self._logger.warning("RLBOT_SPAWN_IDS environment variable not set")
        else:
            self._logger.info("Spawn ID: %s", spawn_ids)
            self.spawn_ids = [int(id) for id in spawn_ids.split(",")]

        self._game_interface = SocketRelay(logger=self._logger)
        self._game_interface.match_settings_handlers.append(self._handle_match_settings)
        self._game_interface.field_info_handlers.append(self._handle_field_info)
        self._game_interface.match_communication_handlers.append(
            self.handle_match_communication
        )
        self._game_interface.ball_prediction_handlers.append(
            self._handle_ball_prediction
        )
        self._game_interface.packet_handlers.append(self._handle_packet)

        self._packet_thread = Thread(target=self._packet_processor, daemon=True)
        self._packet_thread.start()

        self.renderer = Renderer(self._game_interface)

    def _initialize_agent(self):
        try:
            self.initialize_agent()
        except Exception as e:
            self._logger.critical(
                "Hivemind %s failed to initialize due the following error: %s",
                "Unknown" if len(self.names) == 0 else self.names[0],
                e,
            )
            print_exc()
            exit()

        self._initialized_bot = True
        self._game_interface.send_init_complete(flat.InitComplete(self.spawn_ids[0]))

    def _handle_match_settings(self, match_settings: flat.MatchSettings):
        self.match_settings = match_settings
        self._has_match_settings = True

        # search match settings for our spawn ids
        for i, player in enumerate(self.match_settings.player_configurations):
            if player.spawn_id in self.spawn_ids:
                self.team = player.team
                self.names.append(player.name)
                self.loggers[i] = get_logger(player.name)

        if not self._initialized_bot and self._has_field_info:
            self._initialize_agent()

    def _handle_field_info(self, field_info: flat.FieldInfo):
        self.field_info = field_info
        self._has_field_info = True

        if not self._initialized_bot and self._has_match_settings:
            self._initialize_agent()

    def _handle_ball_prediction(self, ball_prediction: flat.BallPrediction):
        self._lastest_prediction = ball_prediction

    def _handle_packet(self, packet: flat.GameTickPacket):
        self._latest_packet = packet
        self._packet_event.set()

    def _packet_preprocess(self, packet: flat.GameTickPacket) -> bool:
        if len(self.indicies) != len(self.spawn_ids) or any(
            packet.players[i].spawn_id not in self.spawn_ids for i in self.indicies
        ):
            self.indicies = [
                i
                for i, player in enumerate(packet.players)
                if player.spawn_id in self.spawn_ids
            ]

            if len(self.indicies) != len(self.spawn_ids):
                return False

        # print([player.name for player in packet.players], self.spawn_ids, self.indicies)
        return True

    def _packet_processor(self):
        while self._run_packet_thread:
            self._packet_event.wait()

            self.ball_prediction = self._lastest_prediction
            packet = self._latest_packet

            self._packet_event.clear()

            if not self._packet_preprocess(self._latest_packet):
                continue

            try:
                controller = self.get_outputs(packet)
            except Exception as e:
                self._logger.error(
                    "Hivemind (with %s) returned an error to RLBot: %s", self.names, e
                )
                print_exc()
                continue

            for index, controller in controller.items():
                player_input = flat.PlayerInput(index, controller)
                self._game_interface.send_player_input(player_input)

    def run(
        self,
        wants_match_communcations: bool = True,
        wants_ball_predictions: bool = True,
    ):
        try:
            self._game_interface.connect_and_run(
                wants_match_communcations,
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

    def get_outputs(
        self, packet: flat.GameTickPacket
    ) -> dict[int, flat.ControllerState]:
        """
        Where all the logic of your bot gets its input and returns its output.
        """
        raise NotImplementedError
