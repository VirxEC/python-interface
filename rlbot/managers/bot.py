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
    _has_player_mapping = False

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
        self._game_interface.controllable_team_info_handlers.append(
            self._handle_player_mappings
        )
        self._game_interface.packet_handlers.append(self._handle_packet)

        self.renderer = Renderer(self._game_interface)

    def _initialize(self):
        # search match settings for our name
        for player in self.match_settings.player_configurations:
            if player.spawn_id == self.spawn_id:
                self.name = player.name
                self.logger = get_logger(self.name)
                break

        try:
            self.initialize()
        except Exception as e:
            self.logger.critical(
                "Bot %s failed to initialize due the following error: %s", self.name, e
            )
            print_exc()
            exit()

        self._initialized_bot = True
        self._game_interface.send_init_complete()

    def _handle_match_settings(self, match_settings: flat.MatchSettings):
        self.match_settings = match_settings
        self._has_match_settings = True

        if (
            not self._initialized_bot
            and self._has_field_info
            and self._has_player_mapping
        ):
            self._initialize()

    def _handle_field_info(self, field_info: flat.FieldInfo):
        self.field_info = field_info
        self._has_field_info = True

        if (
            not self._initialized_bot
            and self._has_match_settings
            and self._has_player_mapping
        ):
            self._initialize()

    def _handle_player_mappings(self, player_mappings: flat.ControllableTeamInfo):
        self.team = player_mappings.team
        controllable = player_mappings.controllables[0]
        self.spawn_id = controllable.spawn_id
        self.index = controllable.index
        self._has_player_mapping = True

        if (
            not self._initialized_bot
            and self._has_match_settings
            and self._has_field_info
        ):
            self._initialize()

    def _handle_ball_prediction(self, ball_prediction: flat.BallPrediction):
        self._latest_prediction = ball_prediction

    def _handle_packet(self, packet: flat.GamePacket):
        self._latest_packet = packet

    def _packet_processor(self, packet: flat.GamePacket):
        if len(packet.players) <= self.index:
            return

        self.ball_prediction = self._latest_prediction

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

            # custom message handling logic
            # this reads all data in the socket until there's no more immediately available
            # checks if there was a GamePacket in the data, and if so, processes it
            # then sets the socket to non-blocking and waits for more data
            # if there was no GamePacket, it sets to blocking and waits for more data
            while True:
                try:
                    self._game_interface.handle_incoming_messages(True)

                    # a clean exit means that the socket was closed
                    break
                except BlockingIOError:
                    # the socket was still open,
                    # but we don't know if data was read
                    pass

                # check data was read that needs to be processed
                if self._latest_packet is None:
                    # there's no data we need to process
                    # data is coming, but we haven't gotten it yet - wait for it
                    # after `handle_incoming_messages` gets it's first message,
                    # it will set the socket back to non-blocking on its own
                    # that will ensure that `BlockingIOError` gets raised
                    # when it's done reading the next batch of messages
                    self._game_interface.socket.setblocking(True)
                    continue

                # process the packet that we got
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

        For use as a loadout generator, call inside of `initialize`.
        Will be ignored if called outside of `initialize` when state setting is disabled.
        """
        self._game_interface.send_set_loadout(flat.SetLoadout(spawn_id, loadout))

    def initialize(self):
        """
        Called for all heaver initialization that needs to happen.
        Field info, match settings, name, index, and team are fully loaded at this point, and won't return garbage data.
        """

    def retire(self):
        """Called after the game ends"""

    def get_output(self, packet: flat.GamePacket) -> flat.ControllerState:
        """
        Where all the logic of your bot gets its input and returns its output.
        """
        raise NotImplementedError
