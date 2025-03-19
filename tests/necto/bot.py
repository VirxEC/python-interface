import numpy as np
import torch
from agent import Agent
from necto_obs import NectoObsBuilder
from rlgym_compat import V1GameState

from rlbot.flat import ControllerState, GamePacket, MatchPhase, Vector3
from rlbot.managers import Bot

KICKOFF_CONTROLS = (
    11 * 4 * [ControllerState(throttle=1, boost=True)]
    + 4 * 4 * [ControllerState(throttle=1, boost=True, steer=-1)]
    + 2 * 4 * [ControllerState(throttle=1, jump=True, boost=True)]
    + 1 * 4 * [ControllerState(throttle=1, boost=True)]
    + 1 * 4 * [ControllerState(throttle=1, yaw=0.8, pitch=-0.7, jump=True, boost=True)]
    + 13 * 4 * [ControllerState(throttle=1, pitch=1, boost=True)]
    + 10 * 4 * [ControllerState(throttle=1, roll=1, pitch=0.5)]
)

KICKOFF_NUMPY = np.array(
    [
        [
            scs.throttle,
            scs.steer,
            scs.pitch,
            scs.yaw,
            scs.roll,
            scs.jump,
            scs.boost,
            scs.handbrake,
        ]
        for scs in KICKOFF_CONTROLS
    ]
)


class Necto(Bot):
    agent = Agent()
    tick_skip = 8

    # Beta controls randomness:
    # 1=best action, 0.5=sampling from probability, 0=random, -1=worst action, or anywhere inbetween
    beta = 1
    render = False
    hardcoded_kickoffs = True

    prev_frame = 0
    controls = ControllerState()
    action = np.zeros(8)
    update_action = True
    kickoff_index = -1
    ticks = tick_skip  # So we take an action the first tick

    def initialize(self):
        # Initialize the rlgym GameState object now that the game is active and the info is available
        self.obs_builder = NectoObsBuilder(self.field_info)

        if len(self.field_info.boost_pads) != 34:
            self.logger.warning(
                "The standard number of boost pads is 34, but this map has %d:%s",
                len(self.field_info.boost_pads),
                "\n".join(map(str, self.field_info.boost_pads)),
            )

        self.game_state = V1GameState(
            self.field_info, self.match_config, self.tick_skip
        )

        self.logger.warning(
            "Remember to run Necto at 120fps with vsync off! "
            "Stable 240/360 is second best if that's better for your eyes"
        )
        self.logger.info(
            "Also check out the RLGym Twitch stream to watch live bot training and occasional showmatches!"
        )

    def render_attention_weights(
        self,
        weights: list[torch.Tensor],
        obs: tuple[np.ndarray, np.ndarray, np.ndarray],
    ):
        mean_weights = torch.mean(torch.stack(weights), dim=0).numpy()[0][0]

        top = sorted(
            range(len(mean_weights)), key=lambda i: mean_weights[i], reverse=True
        )
        top.remove(1)  # Self

        self.renderer.begin_rendering("attention_weights")

        invert = np.array([-1, -1, 1]) if self.team == 1 else np.ones(3)
        loc = obs[0][0, 0, 5:8] * 2300 * invert
        mx = mean_weights[~(np.arange(len(mean_weights)) == 1)].max()
        c = 1
        for i in top[:3]:
            weight = mean_weights[i] / mx
            dest = loc + obs[1][0, i, 5:8] * 2300 * invert
            color = self.renderer.create_color(
                round(255 * (1 - weight)),
                255,
                round(255 * (1 - weight)),
            )

            self.renderer.draw_string_3d(
                str(c),
                Vector3(*dest),
                2,
                color,
            )

            c += 1

            self.renderer.draw_line_3d(
                Vector3(*loc),
                Vector3(*dest),
                color,
            )

        self.renderer.end_rendering()

    def get_output(self, packet: GamePacket) -> ControllerState:
        cur_frame = packet.match_info.frame_num
        ticks_elapsed = cur_frame - self.prev_frame
        self.prev_frame = cur_frame

        self.ticks += ticks_elapsed

        if len(packet.balls) == 0:
            return self.controls

        self.game_state.update(packet)

        if self.update_action == 1 and len(self.game_state.players) > self.index:
            self.update_action = 0

            player = self.game_state.players[self.index]
            teammates = [
                p
                for p in self.game_state.players
                if p.team_num == self.team and p != player
            ]
            opponents = [p for p in self.game_state.players if p.team_num != self.team]

            self.game_state.players = [player] + teammates + opponents

            obs = self.obs_builder.build_obs(player, self.game_state, self.action)

            beta = self.beta
            if packet.match_info.match_phase == MatchPhase.Ended:
                beta = 0  # Celebrate with random actions
            self.action, weights = self.agent.act(obs, beta)

            if self.render:
                self.render_attention_weights(weights, obs)

        if self.ticks >= self.tick_skip:
            self.ticks = 0
            self.update_controls(self.action)
            self.update_action = 1

        if self.hardcoded_kickoffs:
            self.maybe_do_kickoff(packet, ticks_elapsed)

        return self.controls

    def maybe_do_kickoff(self, packet: GamePacket, ticks_elapsed: int):
        if packet.match_info.match_phase == MatchPhase.Kickoff:
            if self.kickoff_index >= 0:
                self.kickoff_index += round(ticks_elapsed)
            elif self.kickoff_index == -1:
                is_kickoff_taker = False
                ball_pos = np.array(
                    [
                        packet.balls[0].physics.location.x,
                        packet.balls[0].physics.location.y,
                    ]
                )
                positions = np.array(
                    [
                        [car.physics.location.x, car.physics.location.y]
                        for car in packet.players
                    ]
                )
                distances = np.linalg.norm(positions - ball_pos, axis=1)
                if abs(distances.min() - distances[self.index]) <= 10:
                    is_kickoff_taker = True
                    indices = np.argsort(distances)
                    for index in indices:
                        if (
                            abs(distances[index] - distances[self.index]) <= 10
                            and packet.players[index].team == self.team
                            and index != self.index
                        ):
                            if self.team == 0:
                                is_left = positions[index, 0] < positions[self.index, 0]
                            else:
                                is_left = positions[index, 0] > positions[self.index, 0]
                            if not is_left:
                                is_kickoff_taker = False  # Left goes

                self.kickoff_index = 0 if is_kickoff_taker else -2

            if (
                0 <= self.kickoff_index < len(KICKOFF_NUMPY)
                and packet.balls[0].physics.location.y == 0
            ):
                action = KICKOFF_NUMPY[self.kickoff_index]
                self.action = action
                self.update_controls(self.action)
        else:
            self.kickoff_index = -1

    def update_controls(self, action: np.ndarray):
        self.controls.throttle = action[0]
        self.controls.steer = action[1]
        self.controls.pitch = action[2]
        self.controls.yaw = action[3]
        self.controls.roll = action[4]
        self.controls.jump = bool(action[5] > 0)
        self.controls.boost = bool(action[6] > 0)
        self.controls.handbrake = bool(action[7] > 0)


if __name__ == "__main__":
    Necto("rlgym/necto").run(
        wants_match_communications=False, wants_ball_predictions=False
    )
