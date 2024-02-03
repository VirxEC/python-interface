from rlbot import flat
from rlbot.interface import SocketRelay
from rlbot.managers.rendering import RenderingManager
from rlbot.utils.logging import get_logger


class ScriptManager:
    """
    A convenience class for building scripts on top of.
    """

    def __init__(self, name):
        self.name = name
        self.logger = get_logger(name)

        self.game_interface = SocketRelay(logger=self.logger)
        self.game_interface.match_settings_handlers.append(self.handle_match_settings)
        self.game_interface.field_info_handlers.append(self.handle_field_info)
        self.game_interface.packet_handlers.append(self.handle_packet)

        self.renderer = RenderingManager(self.game_interface)

    def set_game_state(self, game_state: flat.DesiredGameState):
        self.game_interface.send_game_state(game_state)

    def run(self):
        self.game_interface.connect_and_run(True, True, True)
        del self.game_interface

    def handle_match_settings(self, match_settings: flat.MatchSettings):
        pass

    def handle_field_info(self, field_info: flat.FieldInfo):
        pass

    def handle_packet(self, packet: flat.GameTickPacket):
        pass
