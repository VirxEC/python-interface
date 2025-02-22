import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from socket import IPPROTO_TCP, TCP_NODELAY, socket
from threading import Thread
from typing import Optional

from rlbot import flat
from rlbot.utils.logging import get_logger

MAX_SIZE_2_BYTES = 2**16 - 1
# The default IP to connect to RLBotServer on
RLBOT_SERVER_IP = "127.0.0.1"
# The default port we can expect RLBotServer to be listening on
RLBOT_SERVER_PORT = 23234


class SocketDataType(IntEnum):
    """
    See https://github.com/RLBot/core/blob/master/RLBotCS/Types/DataType.cs
    and https://wiki.rlbot.org/framework/sockets-specification/#data-types
    """

    NONE = 0
    GAME_PACKET = 1
    FIELD_INFO = 2
    START_COMMAND = 3
    MATCH_CONFIGURATION = 4
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
    CONTROLLABLE_TEAM_INFO = 15


@dataclass(repr=False, eq=False, frozen=True, match_args=False, slots=True)
class SocketMessage:
    type: SocketDataType
    data: bytes


class MsgHandlingResult(IntEnum):
    TERMINATED = 0
    NO_INCOMING_MSGS = 1
    MORE_MSGS_QUEUED = 2


class SocketRelay:
    """
    The SocketRelay provides an abstraction over the direct communication with
    the RLBotServer making it easy to send the various types of messages.

    Common use patterns are covered by `bot.py`, `script.py`, `hivemind.py`, and `match.py`
    from `rlbot.managers`.
    """

    is_connected = False
    _running = False
    """Indicates whether a messages are being handled by the `run` loop (potentially in a background thread)"""
    _ball_pred = flat.BallPrediction()

    on_connect_handlers: list[Callable[[], None]] = []
    packet_handlers: list[Callable[[flat.GamePacket], None]] = []
    field_info_handlers: list[Callable[[flat.FieldInfo], None]] = []
    match_config_handlers: list[Callable[[flat.MatchConfiguration], None]] = []
    match_comm_handlers: list[Callable[[flat.MatchComm], None]] = []
    ball_prediction_handlers: list[Callable[[flat.BallPrediction], None]] = []
    controllable_team_info_handlers: list[
        Callable[[flat.ControllableTeamInfo], None]
    ] = []
    raw_handlers: list[Callable[[SocketMessage], None]] = []

    def __init__(
        self,
        agent_id: str,
        connection_timeout: float = 120,
        logger: Optional[logging.Logger] = None,
    ):
        self.agent_id = agent_id
        self.connection_timeout = connection_timeout
        self.logger = get_logger("interface") if logger is None else logger

        self.socket = socket()

        # Allow sending packets before getting a response from core
        self.socket.setsockopt(IPPROTO_TCP, TCP_NODELAY, 1)

    def __del__(self):
        self.socket.close()

    @staticmethod
    def _int_to_bytes(val: int) -> bytes:
        return val.to_bytes(2, byteorder="big")

    def _read_int(self) -> int:
        return int.from_bytes(self._read_exact(2), "big")

    def _read_exact(self, n: int) -> bytes:
        buff = bytearray(n)
        view = memoryview(buff)

        pos = 0
        while pos < n:
            cr = self.socket.recv_into(view[pos:])
            if cr == 0:
                raise EOFError
            pos += cr
        return bytes(buff)

    def read_message(self) -> SocketMessage:
        type_int = self._read_int()
        size = self._read_int()
        data = self._read_exact(size)
        return SocketMessage(SocketDataType(type_int), data)

    def send_bytes(self, data: bytes, data_type: SocketDataType):
        assert self.is_connected, "Connection has not been established"

        size = len(data)
        if size > MAX_SIZE_2_BYTES:
            self.logger.error(
                "Couldn't send %s message because it was too big!", data_type.name
            )
            return

        message = self._int_to_bytes(data_type) + self._int_to_bytes(size) + data
        self.socket.sendall(message)

    def send_init_complete(self):
        self.send_bytes(bytes(), SocketDataType.INIT_COMPLETE)

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

    def start_match(self, match_config: Path | flat.MatchConfiguration):
        self.logger.info("Python interface is attempting to start match...")

        match match_config:
            case Path() as path:
                string_path = str(path.absolute().resolve())
                flatbuffer = flat.StartCommand(string_path).pack()
                flat_type = SocketDataType.START_COMMAND
            case flat.MatchConfiguration() as settings:
                flatbuffer = settings.pack()
                flat_type = SocketDataType.MATCH_CONFIGURATION
            case _:
                raise ValueError(
                    "Expected MatchSettings or path to match settings toml file"
                )

        self.send_bytes(flatbuffer, flat_type)

    def connect(
        self,
        *,
        wants_match_communications: bool,
        wants_ball_predictions: bool,
        close_between_matches: bool = True,
        rlbot_server_ip: str = RLBOT_SERVER_IP,
        rlbot_server_port: int = RLBOT_SERVER_PORT,
    ):
        """
        Connects to the RLBot server specifying the given settings.

        - wants_match_communications: Whether match communication messages should be sent to this process.
        - wants_ball_predictions: Whether ball prediction messages should be sent to this process.
        - close_between_matches: Whether RLBot should close this connection between matches, specifically upon
            `StartMatch` and `StopMatch` messages, since RLBot does not actually detect the ending of matches.
        """
        assert not self.is_connected, "Connection has already been established"

        self.socket.settimeout(self.connection_timeout)
        try:
            begin_time = time.time()
            next_warning = 10
            while time.time() < begin_time + self.connection_timeout:
                try:
                    self.socket.connect((rlbot_server_ip, rlbot_server_port))
                    self.is_connected = True
                    break
                except ConnectionRefusedError:
                    time.sleep(0.1)
                except ConnectionAbortedError:
                    time.sleep(0.1)
                if time.time() > begin_time + next_warning:
                    next_warning *= 2
                    self.logger.warning(
                        "Connection is being refused/aborted. Trying again ..."
                    )
            if not self.is_connected:
                raise ConnectionRefusedError(
                    "Connection was refused/aborted repeatedly! "
                    "Ensure that Rocket League and the RLBotServer is running. "
                    "Try calling `ensure_server_started()` before connecting."
                )
        except TimeoutError as e:
            raise TimeoutError(
                "Took too long to connect to the RLBot! "
                "Ensure that Rocket League and the RLBotServer is running."
                "Try calling `ensure_server_started()` before connecting."
            ) from e
        finally:
            self.socket.settimeout(None)

        self.logger.info(
            "SocketRelay connected to port %s from port %s!",
            rlbot_server_port,
            self.socket.getsockname()[1],
        )

        for handler in self.on_connect_handlers:
            handler()

        flatbuffer = flat.ConnectionSettings(
            agent_id=self.agent_id,
            wants_ball_predictions=wants_ball_predictions,
            wants_comms=wants_match_communications,
            close_between_matches=close_between_matches,
        ).pack()
        self.send_bytes(flatbuffer, SocketDataType.CONNECTION_SETTINGS)

    def run(self, *, background_thread: bool = False):
        """
        Handle incoming messages until disconnected.
        If `background_thread` is `True`, a background thread will be started for this.
        """
        assert self.is_connected, "Connection has not been established"
        assert not self._running, "Message handling is already running"
        if background_thread:
            Thread(target=self.run).start()
        else:
            self._running = True
            while self._running and self.is_connected:
                self._running = (
                    self.handle_incoming_messages(blocking=True)
                    != MsgHandlingResult.TERMINATED
                )
            self._running = False

    def handle_incoming_messages(self, blocking: bool = False) -> MsgHandlingResult:
        """
        Empties queue of incoming messages (should be called regularly, see `run`).
        Optionally blocking, ensuring that at least one message will be handled.

        First boolean returns true message handling should continue running, and
        false if RLBotServer has asked us to shut down or an error happened.

        Second boolean returns true if there might be more messages to handle without a delay.
        """
        assert self.is_connected, "Connection has not been established"
        try:
            self.socket.setblocking(blocking)
            incoming_message = self.read_message()
            try:
                return self.handle_incoming_message(incoming_message)
            except flat.InvalidFlatbuffer as e:
                self.logger.error(
                    "Error while unpacking message of type %s (%s bytes): %s",
                    incoming_message.type.name,
                    len(incoming_message.data),
                    e,
                )
                return MsgHandlingResult.TERMINATED
            except Exception as e:
                self.logger.error(
                    "Unexpected error while handling message of type %s: %s",
                    incoming_message.type.name,
                    e,
                )
                return MsgHandlingResult.TERMINATED
        except BlockingIOError:
            # No incoming messages and blocking==False
            return MsgHandlingResult.NO_INCOMING_MSGS
        except:
            self.logger.error("SocketRelay disconnected unexpectedly!")
            return MsgHandlingResult.TERMINATED

    def handle_incoming_message(
        self, incoming_message: SocketMessage
    ) -> MsgHandlingResult:
        """
        Handles a messages by passing it to the relevant handlers.
        Returns True if the message was NOT a shutdown request (i.e. NONE).
        """

        for raw_handler in self.raw_handlers:
            raw_handler(incoming_message)

        match incoming_message.type:
            case SocketDataType.NONE:
                return MsgHandlingResult.TERMINATED
            case SocketDataType.GAME_PACKET:
                if len(self.packet_handlers) > 0:
                    packet = flat.GamePacket.unpack(incoming_message.data)
                    for handler in self.packet_handlers:
                        handler(packet)
            case SocketDataType.FIELD_INFO:
                if len(self.field_info_handlers) > 0:
                    field_info = flat.FieldInfo.unpack(incoming_message.data)
                    for handler in self.field_info_handlers:
                        handler(field_info)
            case SocketDataType.MATCH_CONFIGURATION:
                if len(self.match_config_handlers) > 0:
                    match_settings = flat.MatchConfiguration.unpack(
                        incoming_message.data
                    )
                    for handler in self.match_config_handlers:
                        handler(match_settings)
            case SocketDataType.MATCH_COMMUNICATION:
                if len(self.match_comm_handlers) > 0:
                    match_comm = flat.MatchComm.unpack(incoming_message.data)
                    for handler in self.match_comm_handlers:
                        handler(match_comm)
            case SocketDataType.BALL_PREDICTION:
                if len(self.ball_prediction_handlers) > 0:
                    ball_prediction = self._ball_pred.unpack_with(incoming_message.data)
                    for handler in self.ball_prediction_handlers:
                        handler(ball_prediction)
            case SocketDataType.CONTROLLABLE_TEAM_INFO:
                if len(self.controllable_team_info_handlers) > 0:
                    player_mappings = flat.ControllableTeamInfo.unpack(
                        incoming_message.data
                    )
                    for handler in self.controllable_team_info_handlers:
                        handler(player_mappings)
            case _:
                pass

        return MsgHandlingResult.MORE_MSGS_QUEUED

    def disconnect(self):
        if not self.is_connected:
            self.logger.warning("Asked to disconnect but was already disconnected.")
            return

        self.send_bytes(bytes([1]), SocketDataType.NONE)
        timeout = 5.0
        while self._running and timeout > 0:
            time.sleep(0.1)
            timeout -= 0.1
        if timeout <= 0:
            self.logger.critical("RLBot is not responding to our disconnect request!?")
            self._running = False

        assert (
            not self._running
        ), "Disconnect request or timeout should have set self._running to False"
        self.is_connected = False
