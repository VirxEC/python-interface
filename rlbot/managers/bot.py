import os
from traceback import print_exc

from rlbot import flat
from rlbot.interface import SocketRelay
from rlbot.managers.rendering import RenderingManager
from rlbot.utils.logging import DEFAULT_LOGGER, get_logger


class Bot:
    """
    A convenience class for building bots on top of.
    """
    logger = DEFAULT_LOGGER

    index: int = -1
    team: int = -1
    name: str = ""

    initialized_bot = False
    has_match_settings = False
    has_field_info = False

    match_settings = flat.MatchSettings()
    field_info = flat.FieldInfo()

    def __init__(self):
        spawn_id = os.environ.get("BOT_SPAWN_ID")

        if spawn_id is None:
            self.logger.warning("BOT_SPAWN_ID environment variable not set")
            self.spawn_id: int = 0
        else:
            self.spawn_id: int = int(spawn_id)
            self.logger.info(f"Spawn ID: {self.spawn_id}")

        self.game_interface = SocketRelay(logger=self.logger)
        self.game_interface.match_settings_handlers.append(self._handle_match_settings)
        self.game_interface.field_info_handlers.append(self._handle_field_info)
        self.game_interface.packet_handlers.append(self._handle_packet)

        self.renderer = RenderingManager(self.game_interface)

    def _handle_match_settings(self, match_settings: flat.MatchSettings):
        self.match_settings = match_settings
        self.has_match_settings = True

        # search match settings for our spawn id
        for player in self.match_settings.player_configurations:
            if player.spawn_id == self.spawn_id:
                self.team = player.team
                self.name = player.name
                self.logger = get_logger(self.name)
                break

        if not self.initialized_bot and self.has_field_info:
            self.initialize_agent()
            self.initialized_bot = True

    def _handle_field_info(self, field_info: flat.FieldInfo):
        self.field_info = field_info
        self.has_field_info = True

        if not self.initialized_bot and self.has_match_settings:
            self.initialize_agent()
            self.initialized_bot = True

    def _handle_packet(self, packet: flat.GameTickPacket):
        if not self.initialized_bot:
            return

        if self.index == -1:
            for i, player in enumerate(packet.players):
                if player.spawn_id == self.spawn_id:
                    self.index = i
                    break

            if self.index == -1:
                return

        try:
            controller = self.get_output(packet)
        except Exception as e:
            self.logger.error(f"Bot {self.name} returned an error to RLBot: {e}")
            print_exc()
            return

        player_input = flat.PlayerInput(self.index, controller)
        self.game_interface.send_player_input(player_input)

    def run(self):
        self.game_interface.connect_and_run(True, True, True)
        self.retire()
        del self.game_interface

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

    def set_game_state(self, game_state: flat.DesiredGameState):
        """
        Sets the game to the given desired state.
        """
        self.game_interface.send_game_state(game_state)

    def initialize_agent(self):
        """
        Called for all heaver initialization that needs to happen.
        Field info and match settings are fully loaded at this point, and won't return garbage data.
        """
        pass

    def retire(self):
        """Called after the game ends"""
        pass

    def get_output(self, game_tick_packet: flat.GameTickPacket) -> flat.ControllerState:
        """
        Where all the logic of your bot gets its input and returns its output.
        """
        return flat.ControllerState()
