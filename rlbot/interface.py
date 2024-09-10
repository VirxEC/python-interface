import logging
from enum import IntEnum
from pathlib import Path
from socket import IPPROTO_TCP, TCP_NODELAY, socket, timeout
from threading import Thread
from time import sleep
from typing import Callable, Optional

from rlbot import flat
from rlbot.utils.logging import get_logger

# We can connect to RLBotServer on this port.
RLBOT_SERVER_PORT = 23234


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
    CONNECTION_SETTINGS = 11
    STOP_COMMAND = 12
    SET_LOADOUT = 13
    INIT_COMPLETE = 14


MAX_SIZE_2_BYTES = 2**16 - 1


def int_to_bytes(val: int) -> bytes:
    return val.to_bytes(2, byteorder="big")


def int_from_bytes(bytes: bytes) -> int:
    return int.from_bytes(bytes, "big")


class SocketMessage:
    def __init__(self, type: int, data: bytes):
        self.type = SocketDataType(type)
        self.data = data


def read_from_socket(s: socket) -> SocketMessage:
    type_int = int_from_bytes(s.recv(2))
    size = int_from_bytes(s.recv(2))
    data = s.recv(size)
    return SocketMessage(type_int, data)


class SocketRelay:
    is_connected = False
    _should_continue = True

    on_connect_handlers: list[Callable[[], None]] = []
    packet_handlers: list[Callable[[flat.GameTickPacket], None]] = []
    field_info_handlers: list[Callable[[flat.FieldInfo], None]] = []
    match_settings_handlers: list[Callable[[flat.MatchSettings], None]] = []
    match_communication_handlers: list[Callable[[flat.MatchComm], None]] = []
    ball_prediction_handlers: list[Callable[[flat.BallPrediction], None]] = []
    raw_handlers: list[Callable[[SocketMessage], None]] = []

    def __init__(
        self, connection_timeout: float = 120, logger: Optional[logging.Logger] = None
    ):
        self.connection_timeout = connection_timeout
        self.logger = get_logger("interface") if logger is None else logger

        self.socket = socket()
        self.socket.setsockopt(IPPROTO_TCP, TCP_NODELAY, 1)

    def __del__(self):
        self.socket.close()

    def send_bytes(self, data: bytes, data_type: SocketDataType):
        size = len(data)
        if size > MAX_SIZE_2_BYTES:
            self.logger.error(
                "Couldn't send a %s message because it was too big!", data_type
            )
            return

        message = int_to_bytes(data_type) + int_to_bytes(size) + data
        self.socket.sendall(message)

    def send_init_complete(self, init_complete: flat.InitComplete):
        self.send_bytes(init_complete.pack(), SocketDataType.INIT_COMPLETE)

    def send_set_loadout(self, set_loadout: flat.SetLoadout):
        self.send_bytes(set_loadout.pack(), SocketDataType.SET_LOADOUT)

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

    def start_match(
        self,
        match_config: Path | flat.MatchSettings,
        rlbot_server_port: int = RLBOT_SERVER_PORT,
    ):
        match match_config:
            case Path() as path:
                string_path = str(path.absolute().resolve())
                flatbuffer = flat.StartCommand(string_path).pack()
                flat_type = SocketDataType.START_COMMAND
            case flat.MatchSettings() as settings:
                flatbuffer = settings.pack()
                flat_type = SocketDataType.MATCH_SETTINGS

        def connect_handler():
            self.send_bytes(flatbuffer, flat_type)

        self.run_after_connect(connect_handler, rlbot_server_port)

    def run_after_connect(
        self,
        handler: Callable[[], None],
        rlbot_server_port: int = RLBOT_SERVER_PORT,
    ):
        if self.is_connected:
            handler()
        else:
            self.on_connect_handlers.append(handler)
            try:
                self.connect_and_run(False, False, False, True, rlbot_server_port)
            except timeout as e:
                raise TimeoutError(
                    "Took too long to connect to the RLBot executable!"
                ) from e

    def connect(
        self,
        wants_match_communcations: bool,
        wants_ball_predictions: bool,
        close_after_match: bool = True,
        rlbot_server_port: int = RLBOT_SERVER_PORT,
    ):
        """
        Connects to the socket and sends the connection settings.

        NOTE: Bad things happen if the buffer is allowed to fill up. Ensure
        `handle_incoming_messages` is called frequently enough to prevent this.
        """
        self.socket.settimeout(self.connection_timeout)
        for _ in range(int(self.connection_timeout * 10)):
            try:
                self.socket.connect(("127.0.0.1", rlbot_server_port))
                break
            except ConnectionRefusedError:
                sleep(0.1)
            except ConnectionAbortedError:
                sleep(0.1)

        self.socket.settimeout(None)
        self.is_connected = True
        self.logger.info(
            "Socket manager connected to port %s from port %s!",
            rlbot_server_port,
            self.socket.getsockname()[1],
        )

        for handler in self.on_connect_handlers:
            handler()

        flatbuffer = flat.ConnectionSettings(
            wants_ball_predictions,
            wants_match_communcations,
            close_after_match,
        ).pack()
        self.send_bytes(flatbuffer, SocketDataType.CONNECTION_SETTINGS)

    def connect_and_run(
        self,
        wants_match_communcations: bool,
        wants_ball_predictions: bool,
        close_after_match: bool = True,
        only_wait_for_ready: bool = False,
        rlbot_server_port: int = RLBOT_SERVER_PORT,
    ):
        """
        Connects to the socket and begins a loop that reads messages and calls any handlers
        that have been registered. Connect and run are combined into a single method because
        currently bad things happen if the buffer is allowed to fill up.
        """
        self.connect(
            wants_match_communcations,
            wants_ball_predictions,
            close_after_match,
            rlbot_server_port,
        )

        incoming_message = read_from_socket(self.socket)
        self.handle_incoming_message(incoming_message)

        if only_wait_for_ready:
            Thread(target=self.handle_incoming_messages).start()
        else:
            self.handle_incoming_messages()

    def handle_incoming_messages(self, set_nonblocking_after_recv: bool = False):
        try:
            while self._should_continue:
                incoming_message = read_from_socket(self.socket)

                if set_nonblocking_after_recv:
                    self.socket.setblocking(False)

                try:
                    self.handle_incoming_message(incoming_message)
                except flat.InvalidFlatbuffer as e:
                    self.logger.error(
                        "Error while unpacking message of type %s (%s bytes): %s",
                        incoming_message.type.name,
                        len(incoming_message.data),
                        e,
                    )
                except Exception as e:
                    self.logger.warning(
                        "Unexpected error while handling message of type %s: %s",
                        incoming_message.type.name,
                        e,
                    )
        except BlockingIOError:
            raise BlockingIOError
        except:
            self.logger.error("Socket manager disconnected unexpectedly!")

    def handle_incoming_message(self, incoming_message: SocketMessage):
        for raw_handler in self.raw_handlers:
            raw_handler(incoming_message)

        match incoming_message.type:
            case SocketDataType.NONE:
                self._should_continue = False
            case SocketDataType.GAME_TICK_PACKET:
                if len(self.packet_handlers) > 0:
                    packet = flat.GameTickPacket.unpack(incoming_message.data)
                    for handler in self.packet_handlers:
                        handler(packet)
            case SocketDataType.FIELD_INFO:
                if len(self.field_info_handlers) > 0:
                    field_info = flat.FieldInfo.unpack(incoming_message.data)
                    for handler in self.field_info_handlers:
                        handler(field_info)
            case SocketDataType.MATCH_SETTINGS:
                if len(self.match_settings_handlers) > 0:
                    match_settings = flat.MatchSettings.unpack(incoming_message.data)
                    for handler in self.match_settings_handlers:
                        handler(match_settings)
            case SocketDataType.MATCH_COMMUNICATION:
                if len(self.match_communication_handlers) > 0:
                    match_comm = flat.MatchComm.unpack(incoming_message.data)
                    for handler in self.match_communication_handlers:
                        handler(match_comm)
            case SocketDataType.BALL_PREDICTION:
                if len(self.ball_prediction_handlers) > 0:
                    ball_prediction = flat.BallPrediction.unpack(incoming_message.data)
                    for handler in self.ball_prediction_handlers:
                        handler(ball_prediction)

    def disconnect(self):
        if not self.is_connected:
            self.logger.warning("Asked to disconnect but was already disconnected.")
            return

        self.send_bytes(bytes([1]), SocketDataType.NONE)
        while self._should_continue:
            sleep(0.1)

        self.is_connected = False
