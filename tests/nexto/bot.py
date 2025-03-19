import math
import random

import numpy as np
import torch
from agent import Agent
from nexto_obs import BOOST_LOCATIONS, NextoObsBuilder
from rlgym_compat.v1_game_state import V1GameState as GameState

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

GAME_MODES = [
    "soccer",
    "hoops",
    "dropshot",
    "hockey",
    "rumble",
    "heatseeker",
]


class Nexto(Bot):
    # Beta controls randomness:
    # 1=best action, 0.5=sampling from probability, 0=random, -1=worst action, or anywhere inbetween
    beta = 1
    render = False
    hardcoded_kickoffs = True
    stochastic_kickoffs = True

    agent = Agent()
    tick_skip = 8

    controls = ControllerState()
    action = np.zeros(8)
    update_action = True
    ticks = tick_skip  # So we take an action the first tick
    prev_tick = 0
    kickoff_index = -1
    gamemode = ""

    # toxic handling
    orange_goals = 0
    blue_goals = 0
    demoed_count = 0
    last_frame_ball = None
    last_frame_demod = False
    demo_count = 0
    pester_count = 0
    demoed_tick_count = 0
    demo_callout_count = 0
    last_packet = None

    def __init__(self, is_toxic=False):
        super().__init__()

        self.is_toxic = is_toxic

    def initialize(self):
        # Initialize the rlgym GameState object now that the game is active and the info is available
        self.obs_builder = NextoObsBuilder(field_info=self.field_info)
        self.game_state = GameState(self.field_info)

        self.logger.warning(
            "Remember to run Necto at 120fps with vsync off! "
            "Stable 240/360 is second best if that's better for your eyes"
        )
        self.logger.info(
            "Also check out the RLGym Twitch stream to watch live bot training and occasional showmatches!"
        )

        game_mode_idx = int(self.match_config.game_mode)
        self.gamemode = (
            GAME_MODES[game_mode_idx] if game_mode_idx < len(GAME_MODES) else 0
        )

    def render_attention_weights(self, weights, positions, n=3):
        if weights is None:
            return

        mean_weights = torch.mean(torch.stack(weights), dim=0).numpy()[0][0]

        top = sorted(
            range(len(mean_weights)), key=lambda i: mean_weights[i], reverse=True
        )
        top.remove(0)  # Self

        self.renderer.begin_rendering("attention_weights")

        invert = np.array([-1, -1, 1]) if self.team == 1 else np.ones(3)
        loc = positions[0] * invert
        mx = mean_weights[~(np.arange(len(mean_weights)) == 1)].max()
        c = 1
        for i in top[:n]:
            weight = mean_weights[i] / mx

            dest = positions[i] * invert
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
        if self.is_toxic:
            self.toxicity(packet)

        cur_tick = packet.match_info.frame_num
        ticks_elapsed = cur_tick - self.prev_tick
        self.prev_tick = cur_tick

        self.ticks += ticks_elapsed

        if len(packet.balls) == 0:
            return self.controls

        self.game_state.update(packet)

        if self.update_action and len(self.game_state.players) > self.index:
            self.update_action = False

            player = self.game_state.players[self.index]
            teammates = [
                p
                for p in self.game_state.players
                if p.team_num == self.team and p != player
            ]
            opponents = [p for p in self.game_state.players if p.team_num != self.team]

            self.game_state.players = [player] + teammates + opponents

            # todo add heatseeker later
            if self.gamemode == "heatseeker":
                self._modify_ball_info_for_heatseeker(packet, self.game_state)

            obs = self.obs_builder.build_obs(player, self.game_state, self.action)

            beta = self.beta
            if packet.match_info.match_phase == MatchPhase.Ended:
                beta = 0  # Celebrate with random actions
            if (
                self.stochastic_kickoffs
                and packet.match_info.match_phase == MatchPhase.Kickoff
            ):
                beta = 0.5
            self.action, weights = self.agent.act(obs, beta)

            if self.render:
                positions = np.asarray(
                    [p.car_data.position for p in self.game_state.players]
                    + [self.game_state.ball.position]
                    + list(BOOST_LOCATIONS)
                )
                self.render_attention_weights(weights, positions)

        if self.ticks >= self.tick_skip - 1:
            self.update_controls(self.action)

        if self.ticks >= self.tick_skip:
            self.ticks = 0
            self.update_action = True

        if self.hardcoded_kickoffs:
            self.maybe_do_kickoff(packet, ticks_elapsed)

        return self.controls

    def maybe_do_kickoff(self, packet, ticks_elapsed):
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

    def update_controls(self, action):
        self.controls.throttle = action[0]
        self.controls.steer = action[1]
        self.controls.pitch = action[2]
        self.controls.yaw = action[3]
        self.controls.roll = action[4]
        self.controls.jump = action[5] > 0
        self.controls.boost = action[6] > 0
        self.controls.handbrake = action[7] > 0
        if self.gamemode == "rumble":
            self.controls.use_item = np.random.random() > (
                self.tick_skip / 1200
            )  # On average once every 10 seconds

    def _modify_ball_info_for_heatseeker(
        self, packet: GamePacket, game_state: GameState
    ):
        assert len(self.field_info.goals) == 2
        target_goal = self.field_info.goals[self.team].location
        target_goal = np.array([target_goal.x, target_goal.y, target_goal.z])

        ball_pos = game_state.ball.position
        ball_vel = game_state.ball.linear_velocity
        vel_mag = np.linalg.norm(ball_vel)

        current_dir = ball_vel / vel_mag

        goal_dir = target_goal - ball_pos
        goal_dist = np.linalg.norm(goal_dir)
        goal_dir = goal_dir / goal_dist

        latest_touch_is_team = False

        for p in packet.players:
            if p.latest_touch is None or p.latest_touch.ball_index != 0:
                continue

            if p.team == self.team:
                latest_touch_is_team = True
                break

        self.game_state.ball.linear_velocity = (
            1.1
            * vel_mag
            * (goal_dir + (goal_dir if latest_touch_is_team else current_dir))
            / 2
        )
        self.game_state.inverted_ball.linear_velocity = (
            self.game_state.ball.linear_velocity * np.array([-1, -1, 1])
        )

    def toxicity(self, packet: GamePacket):
        """
        THE SALT MUST FLOW
        """

        # prep the toxic
        scored = False
        scored_on = False
        demoed = False
        demo = False

        player = packet.players[self.index]

        human_mates = [
            p for p in packet.players if p.team == self.team and p.is_bot is False
        ]
        human_opps = [
            p for p in packet.players if p.team != self.team and p.is_bot is False
        ]
        good_goal = [0, -5120] if self.team == 0 else [0, 5120]
        bad_goal = [0, 5120] if self.team == 0 else [0, -5120]

        if (
            player.demolished_timeout == -1 and self.demoed_tick_count == 0
        ):  # and not self.last_frame_demod:
            demoed = True
            self.demoed_tick_count = 120 * 4

        for p in packet.players:
            if (
                p.demolished_timeout == -1
                and p.team != self.team
                and self.demo_callout_count == 0
            ):  # player is closest
                demo = True
                self.demo_callout_count = 120 * 4

        if self.blue_goals != packet.teams[0].score:
            # blue goal!
            self.blue_goals = packet.teams[0].score
            if self.team == 0:
                scored = True
            else:
                scored_on = True

        if self.orange_goals != packet.teams[1].score:
            # orange goal
            self.orange_goals = packet.teams[1].score
            if self.team == 1:
                scored = True
            else:
                scored_on = True

        self.last_packet = packet

        # ** NaCl **

        if scored:
            i = random.randint(0, 6)
            if i == 0:
                self.send_match_comm(b"", display="git gud")
                return
            if i == 1:
                self.send_match_comm(b"", display="Thanks!")
                return

            for p in human_opps:

                d = math.sqrt(
                    (p.physics.location.x - bad_goal[0]) ** 2
                    + (p.physics.location.y - bad_goal[1]) ** 2
                )
                if d < 2000:
                    self.send_match_comm(b"", display="What a save!")
                    i = random.randint(0, 3)
                    if i == 0:
                        self.send_match_comm(b"", display="Wow!")
                        self.send_match_comm(b"", display="What a save!")
                    return

            for p in human_opps:
                d = math.sqrt(
                    (p.physics.location.x - bad_goal[0]) ** 2
                    + (p.physics.location.y - bad_goal[1]) ** 2
                )
                if d > 9000:
                    self.send_match_comm(b"", display="Close one!")
                    return

        if scored_on:
            for p in human_mates:
                d = math.sqrt(
                    (p.physics.location.x - good_goal[0]) ** 2
                    + (p.physics.location.y - good_goal[1]) ** 2
                )
                if d < 3000:
                    i = random.randint(0, 2)
                    if i == 0:
                        self.send_match_comm(b"", display="Nice block!")
                    else:
                        self.send_match_comm(b"", display="What a save!")
                    return

            i = random.randint(0, 3)
            if i == 0:
                self.send_match_comm(b"", display="Lag")
                return
            elif i == 1:
                self.send_match_comm(b"", display="Okay.")
                return

        if demo:
            i = random.randint(0, 2)
            if i == 0:
                self.send_match_comm(b"", display="BOOPING")

            elif i == 1:
                self.send_match_comm(b"", display="Sorry!")

            return

        if demoed:
            self.demo_count += 1
            if self.demo_count >= 5:
                i = random.randint(0, 2)
                if i == 0:
                    self.send_match_comm(b"", display="Wow!")
                self.send_match_comm(b"", display="De-Allocate Yourself")

                return

            if self.demo_count >= 3:
                self.send_match_comm(b"", display="Wow!")
                self.send_match_comm(b"", display="Wow!")

            self.send_match_comm(b"", display="Okay.")
            return

        if len(packet.balls) > 0:
            for p in human_mates:
                onOpponentHalf = False

                if p.team == 1 and p.physics.location.y < 0:
                    onOpponentHalf = True
                elif p.team == 0 and p.physics.location.y > 0:
                    onOpponentHalf = True

                d = math.sqrt(
                    (p.physics.location.x - packet.balls[0].physics.location.x) ** 2
                    + (p.physics.location.y - packet.balls[0].physics.location.y) ** 2
                )
                if d < 1000 and self.pester_count == 0 and onOpponentHalf:
                    self.send_match_comm(b"", display="Take the shot!")
                    self.pester_count = 120 * 7  # spam but not too much
                    return

        if self.demo_callout_count > 0:
            self.demo_callout_count -= 1

        if self.demoed_tick_count > 0:
            self.demoed_tick_count -= 1

        if self.pester_count > 0:
            self.pester_count -= 1


if __name__ == "__main__":
    Nexto().run(wants_match_communications=False, wants_ball_predictions=False)
