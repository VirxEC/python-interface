from typing import List

import numpy as np

from rlbot import flat

from .physics_object import PhysicsObject
from .player_data import PlayerData


class GameState:
    def __init__(self, game_info: flat.FieldInfo):
        self.blue_score = 0
        self.orange_score = 0
        self.players: List[PlayerData] = []
        self._on_ground_ticks = np.zeros(64, dtype=np.float32)
        self._air_time = np.zeros(64, dtype=np.float32)

        self.ball: PhysicsObject = PhysicsObject()
        self.inverted_ball: PhysicsObject = PhysicsObject()

        # List of "booleans" (1 or 0)
        self.boost_pads: np.ndarray = np.zeros(
            len(game_info.boost_pads), dtype=np.float32
        )
        self.inverted_boost_pads: np.ndarray = np.zeros_like(
            self.boost_pads, dtype=np.float32
        )

    def decode(self, packet: flat.GameTickPacket, ticks_elapsed: int=1):
        self.blue_score = packet.teams[0].score
        self.orange_score = packet.teams[1].score

        for i, pad in enumerate(packet.boost_pad_states):
            self.boost_pads[i] = pad.is_active
        self.inverted_boost_pads[:] = self.boost_pads[::-1]

        self.ball.decode_ball_data(packet.ball.physics)
        self.inverted_ball.invert(self.ball)

        self.players = []
        for i, car in enumerate(packet.players):
            player = self._decode_player(car, i, ticks_elapsed)
            self.players.append(player)

            if player.ball_touched:
                self.last_touch = player.car_id

    def _decode_player(
        self, player_info: flat.PlayerInfo, index: int, ticks_elapsed: int
    ) -> PlayerData:
        player_data = PlayerData()

        player_data.car_data.decode_car_data(player_info.physics)
        player_data.inverted_car_data.invert(player_data.car_data)

        if player_info.air_state == flat.AirState.OnGround:
            self._on_ground_ticks[index] = 0
            self._air_time[index] = 0
        else:
            self._on_ground_ticks[index] += ticks_elapsed

            if player_info.air_state == flat.AirState.Jumping:
                self._air_time[index] = 0
            elif player_info.air_state in {flat.AirState.DoubleJumping, flat.AirState.Dodging}:
                self._air_time[index] = 150
            else:
                self._air_time[index] += ticks_elapsed

        player_data.car_id = index
        player_data.team_num = player_info.team
        player_data.is_demoed = player_info.demolished_timeout > 0
        player_data.on_ground = (
            player_info.air_state == flat.AirState.OnGround
            or self._on_ground_ticks[index] <= 6
        )
        player_data.ball_touched = False
        player_data.has_jump = player_info.air_state == flat.AirState.OnGround
        # RLGym does consider the timer/unlimited flip, but i'm to lazy to track that in rlbot
        player_data.has_flip = self._air_time[index] < 150
        player_data.boost_amount = player_info.boost / 100

        return player_data
