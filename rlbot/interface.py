import logging
from enum import IntEnum
from pathlib import Path
from socket import socket, timeout
from threading import Thread
from time import sleep
from typing import Callable, Optional

from rlbot import flat
from rlbot.utils.logging import get_logger

# We can connect to RLBotServer on this port.
RLBOT_SOCKETS_PORT = 23234


class SocketDataType(IntEnum):
    """
    https://wiki.rlbot.org/framework/sockets-specification/#data-types
    """

    NONE = 0
    GAME_TICK_PACKET = 1
    FIELD_INFO = 2
    START_COMMAND = 3
    MATCH_SETTINGS = 4
    PLAYER_INPUT = 5
    DESIRED_GAME_STATE = 6
    RENDER_GROUP = 7
    REMOVE_RENDER_GROUP = 8
    MATCH_COMMUNICATION = 9
    BALL_PREDICTION = 10
    READY_MESSAGE = 11
    MESSAGE_PACKET = 12
    STOP_COMMAND = 13


MAX_SIZE_2_BYTES = 2**16 - 1


def int_to_bytes(val: int) -> bytes:
    return val.to_bytes(2, byteorder="big")


def int_from_bytes(bytes: bytes) -> int:
    return int.from_bytes(bytes, "big")


class SocketMessage:
    def __init__(self, type: SocketDataType, data: bytes):
        self.type = type
        self.data = data


def read_from_socket(s: socket) -> SocketMessage:
    type_int = int_from_bytes(s.recv(2))
    data_type = SocketDataType(type_int)
    size = int_from_bytes(s.recv(2))
    data = s.recv(size)
    return SocketMessage(data_type, data)


class SocketRelay:
    is_connected = False
    _should_continue = True

    on_connect_handlers: list[Callable[[], None]] = []
    packet_handlers: list[Callable[[flat.GameTickPacket], None]] = []
    field_info_handlers: list[Callable[[flat.FieldInfo], None]] = []
    match_settings_handlers: list[Callable[[flat.MatchSettings], None]] = []
    match_communication_handlers: list[Callable[[flat.MatchComm], None]] = []
    ball_prediction_handlers: list[Callable[[flat.BallPrediction], None]] = []
    player_input_change_handlers: list[
        Callable[[flat.PlayerInputChange, float, int], None]
    ] = []
    player_stat_handlers: list[Callable[[flat.PlayerStatEvent, float, int], None]] = []
    player_spectate_handlers: list[
        Callable[[flat.PlayerSpectate, float, int], None]
    ] = []
    raw_handlers: list[Callable[[SocketMessage], None]] = []

    def __init__(
        self, connection_timeout: float = 120, logger: Optional[logging.Logger] = None
    ):
        self.connection_timeout = connection_timeout
        self.logger = get_logger("interface") if logger is None else logger

        self.socket = socket()

    def __del__(self):
        self.socket.close()

    def send_bytes(self, data: bytes, data_type: SocketDataType):
        size = len(data)
        if size > MAX_SIZE_2_BYTES:
            self.logger.error(
                f"Couldn't send a {data_type} message because it was too big!"
            )
            return

        message = int_to_bytes(data_type) + int_to_bytes(size) + data
        self.socket.sendall(message)

    def send_match_comm(self, match_comm: flat.MatchComm):
        self.send_bytes(match_comm.pack(), SocketDataType.MATCH_COMMUNICATION)

    def send_player_input(self, player_input: flat.PlayerInput):
        self.send_bytes(player_input.pack(), SocketDataType.PLAYER_INPUT)

    def send_game_state(self, game_state: flat.DesiredGameState):
        self.send_bytes(game_state.pack(), SocketDataType.DESIRED_GAME_STATE)

    def send_render_group(self, render_group: flat.RenderGroup):
        self.send_bytes(render_group.pack(), SocketDataType.RENDER_GROUP)

    def remove_render_group(self, group_id: int):
        flatbuffer = flat.RemoveRenderGroup(group_id).pack()
        self.send_bytes(flatbuffer, SocketDataType.REMOVE_RENDER_GROUP)

    def stop_match(self, shutdown_server: bool = False):
        flatbuffer = flat.StopCommand(shutdown_server).pack()
        self.send_bytes(flatbuffer, SocketDataType.STOP_COMMAND)

    def start_match(self, match_config_path: Path):
        string_path = str(match_config_path.absolute().resolve())
        flatbuffer = flat.StartCommand(string_path).pack()

        def connect_handler():
            self.send_bytes(flatbuffer, SocketDataType.START_COMMAND)

        self.run_after_connect(connect_handler)

    def run_after_connect(self, handler: Callable[[], None]):
        if self.is_connected:
            handler()
        else:
            self.on_connect_handlers.append(handler)
            try:
                self.connect_and_run(False, False, False, False, True)
            except timeout:
                raise TimeoutError("Took too long to connect to the RLBot executable!")

    def connect_and_run(
        self,
        wants_match_communcations: bool,
        wants_game_messages: bool,
        wants_ball_predictions: bool,
        close_after_match: bool = True,
        only_wait_for_ready: bool = False,
    ):
        """
        Connects to the socket and begins a loop that reads messages and calls any handlers
        that have been registered. Connect and run are combined into a single method because
        currently bad things happen if the buffer is allowed to fill up.
        """
        self.socket.settimeout(self.connection_timeout)
        for _ in range(int(self.connection_timeout * 10)):
            try:
                self.socket.connect(("127.0.0.1", RLBOT_SOCKETS_PORT))
                break
            except ConnectionRefusedError:
                sleep(0.1)
            except ConnectionAbortedError:
                sleep(0.1)

        self.socket.settimeout(None)
        self.is_connected = True
        self.logger.info(
            f"Socket manager connected to port {RLBOT_SOCKETS_PORT} from port {self.socket.getsockname()[1]}!"
        )

        for handler in self.on_connect_handlers:
            handler()

        flatbuffer = flat.ReadyMessage(
            wants_ball_predictions,
            wants_match_communcations,
            wants_game_messages,
            close_after_match,
        ).pack()
        self.send_bytes(flatbuffer, SocketDataType.READY_MESSAGE)

        incoming_message = read_from_socket(self.socket)
        self.handle_incoming_message(incoming_message)

        if only_wait_for_ready:
            Thread(target=self.handle_incoming_messages).start()
        else:
            self.handle_incoming_messages()

    def handle_incoming_messages(self):
        try:
            while self._should_continue:
                incoming_message = read_from_socket(self.socket)
                self.handle_incoming_message(incoming_message)
        except:
            self.logger.error("Socket manager disconnected unexpectedly!")

    def handle_incoming_message(self, incoming_message: SocketMessage):
        for raw_handler in self.raw_handlers:
            raw_handler(incoming_message)

        if incoming_message.type == SocketDataType.NONE:
            self._should_continue = False
        elif (
            incoming_message.type == SocketDataType.GAME_TICK_PACKET
            and len(self.packet_handlers) > 0
        ):
            packet = flat.GameTickPacket.unpack(incoming_message.data)
            for handler in self.packet_handlers:
                handler(packet)
        elif (
            incoming_message.type == SocketDataType.FIELD_INFO
            and len(self.field_info_handlers) > 0
        ):
            field_info = flat.FieldInfo.unpack(incoming_message.data)
            for handler in self.field_info_handlers:
                handler(field_info)
        elif (
            incoming_message.type == SocketDataType.MATCH_SETTINGS
            and len(self.match_settings_handlers) > 0
        ):
            match_settings = flat.MatchSettings.unpack(incoming_message.data)
            for handler in self.match_settings_handlers:
                handler(match_settings)
        elif (
            incoming_message.type == SocketDataType.MATCH_COMMUNICATION
            and len(self.match_communication_handlers) > 0
        ):
            match_comm = flat.MatchComm.unpack(incoming_message.data)
            for handler in self.match_communication_handlers:
                handler(match_comm)
        elif (
            incoming_message.type == SocketDataType.BALL_PREDICTION
            and len(self.ball_prediction_handlers) > 0
        ):
            ball_prediction = flat.BallPrediction.unpack(incoming_message.data)
            for handler in self.ball_prediction_handlers:
                handler(ball_prediction)
        elif incoming_message.type == SocketDataType.MESSAGE_PACKET:
            if (
                len(self.player_stat_handlers) > 0
                or len(self.player_input_change_handlers) > 0
                or len(self.player_spectate_handlers) > 0
            ):
                msg_packet = flat.MessagePacket.unpack(incoming_message.data)

                skip_input_change = len(self.player_input_change_handlers) == 0
                skip_spectate = len(self.player_spectate_handlers) == 0
                skip_stat = len(self.player_stat_handlers) == 0

                if skip_input_change and skip_spectate and skip_stat:
                    return

                for msg in msg_packet.messages:
                    self._handle_game_message(
                        msg.message,
                        msg_packet.game_seconds,
                        msg_packet.frame_num,
                        skip_input_change,
                        skip_spectate,
                        skip_stat,
                    )

    def _handle_game_message(
        self,
        msg: flat.GameMessage,
        game_seconds: float,
        frame_num: int,
        skip_input_change: bool,
        skip_spectate: bool,
        skip_stat: bool,
    ):
        if msg.item is flat.PlayerInputChange:
            if skip_input_change:
                return

            for handler in self.player_input_change_handlers:
                handler(
                    msg.item,
                    game_seconds,
                    frame_num,
                )
        elif msg.item is flat.PlayerSpectate:
            if skip_spectate:
                return

            for handler in self.player_spectate_handlers:
                handler(
                    msg.item,
                    game_seconds,
                    frame_num,
                )
        elif msg.item is flat.PlayerStatEvent:
            if skip_stat:
                return

            for handler in self.player_stat_handlers:
                handler(
                    msg.item,
                    game_seconds,
                    frame_num,
                )

    def disconnect(self):
        if not self.is_connected:
            self.logger.warning("Asked to disconnect but was already disconnected.")
            return

        self.send_bytes(bytes([1]), SocketDataType.NONE)
        while self._should_continue:
            sleep(0.1)

        self.is_connected = False
