from collections import Counter

import numpy as np
from rlgym_compat import BLUE_TEAM, ORANGE_TEAM, V1GameState, V1PlayerData

from rlbot import flat


class NectoObsBuilder:
    _invert = np.array([1] * 5 + [-1, -1, 1] * 5 + [1] * 4)
    _norm = np.array([1.0] * 5 + [2300] * 6 + [1] * 6 + [5.5] * 3 + [1] * 4)

    demo_timers = Counter()
    current_state = np.zeros(1)
    current_qkv = np.zeros(1)
    current_mask = np.zeros(1)

    def __init__(self, field_info: flat.FieldInfo, tick_skip: int = 8):
        self.tick_skip: float = tick_skip
        self.boost_timers = np.zeros(len(field_info.boost_pads))

        self._boost_locations: np.ndarray = np.array(
            [
                [bp.location.x, bp.location.y, bp.location.z]
                for bp in field_info.boost_pads
            ]
        )
        self._boost_types: np.ndarray = np.array(
            [bp.is_full_boost for bp in field_info.boost_pads]
        )

    def reset(self, initial_state: V1GameState):
        self.demo_timers = Counter()
        self.boost_timers = np.zeros(len(initial_state.boost_pads))

    def _maybe_update_obs(self, state: V1GameState):
        if self.boost_timers is None:
            self.reset(state)
        else:
            self.current_state = state

        qkv = np.zeros(
            (1, 1 + len(state.players) + len(state.boost_pads), 24)
        )  # Ball, players, boosts

        # Add ball
        n = 0
        ball = state.ball
        qkv[0, 0, 3] = 1  # is_ball
        qkv[0, 0, 5:8] = ball.position
        qkv[0, 0, 8:11] = ball.linear_velocity
        qkv[0, 0, 17:20] = ball.angular_velocity

        # Add players
        n += 1
        for player in state.players:
            if player.team_num == BLUE_TEAM:
                qkv[0, n, 1] = 1  # is_teammate
            else:
                qkv[0, n, 2] = 1  # is_opponent
            car_data = player.car_data
            qkv[0, n, 5:8] = car_data.position
            qkv[0, n, 8:11] = car_data.linear_velocity
            qkv[0, n, 11:14] = car_data.forward()
            qkv[0, n, 14:17] = car_data.up()
            qkv[0, n, 17:20] = car_data.angular_velocity
            qkv[0, n, 20] = player.boost_amount
            #             qkv[0, n, 21] = player.is_demoed
            qkv[0, n, 22] = player.on_ground
            qkv[0, n, 23] = player.has_flip

            # Different than training to account for varying player amounts
            if self.demo_timers[player.car_id] <= 0:
                self.demo_timers[player.car_id] = 3
            else:
                self.demo_timers[player.car_id] = max(  # type: ignore
                    self.demo_timers[player.car_id] - self.tick_skip / 120, 0
                )
            qkv[0, n, 21] = self.demo_timers[player.car_id] / 10
            n += 1

        # Add boost pads
        n = 1 + len(state.players)
        boost_pads = state.boost_pads
        qkv[0, n:, 4] = 1  # is_boost
        qkv[0, n:, 5:8] = self._boost_locations
        qkv[0, n:, 20] = 0.12 + 0.88 * self._boost_types  # Boost amount
        #         qkv[0, n:, 21] = boost_pads

        # Boost and demo timers
        new_boost_grabs = (boost_pads == 1) & (
            self.boost_timers == 0
        )  # New boost grabs since last frame
        self.boost_timers[new_boost_grabs] = 0.4 + 0.6 * (
            self._boost_locations[new_boost_grabs, 2] > 72
        )
        self.boost_timers *= boost_pads  # Make sure we have zeros right
        qkv[0, 1 + len(state.players) :, 21] = self.boost_timers
        self.boost_timers -= (
            self.tick_skip / 1200
        )  # Pre-normalized, 120 fps for 10 seconds
        self.boost_timers[self.boost_timers < 0] = 0

        # Store results
        self.current_qkv = qkv / self._norm
        mask = np.zeros((1, qkv.shape[1]))
        mask[0, 1 + len(state.players) : 1 + len(state.players)] = 1
        self.current_mask = mask

    def build_obs(
        self, player: V1PlayerData, state: V1GameState, previous_action: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        self._maybe_update_obs(state)
        invert = player.team_num == ORANGE_TEAM

        qkv = self.current_qkv.copy()
        mask = self.current_mask.copy()

        main_n = state.players.index(player) + 1
        qkv[0, main_n, 0] = 1  # is_main
        if invert:
            qkv[0, :, (1, 2)] = qkv[0, :, (2, 1)]  # Swap blue/orange
            qkv *= self._invert  # Negate x and y values

        q = qkv[0, main_n, :]
        q = np.expand_dims(np.concatenate((q, previous_action), axis=0), axis=(0, 1))
        kv = qkv

        # Use relative coordinates
        kv[0, :, 5:11] -= q[0, 0, 5:11]
        return q, kv, mask
