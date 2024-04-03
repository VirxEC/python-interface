import math

from rlbot import flat
from rlbot.managers import Bot


class Vector2:
    def __init__(self, x=0.0, y=0.0):
        self.x = float(x)
        self.y = float(y)

    @staticmethod
    def from_vector3t(vec3: flat.Vector3):
        return Vector2(vec3.x, vec3.y)

    def __add__(self, val):
        return Vector2(self.x + val.x, self.y + val.y)

    def __sub__(self, val):
        return Vector2(self.x - val.x, self.y - val.y)

    def correction_to(self, ideal):
        # The in-game axes are left handed, so use -x
        current_in_radians = math.atan2(self.y, -self.x)
        ideal_in_radians = math.atan2(ideal.y, -ideal.x)

        correction = ideal_in_radians - current_in_radians

        # Make sure we go the 'short way'
        if abs(correction) > math.pi:
            if correction < 0:
                correction += 2 * math.pi
            else:
                correction -= 2 * math.pi

        return correction


def get_car_facing_vector(car):
    pitch = float(car.physics.rotation.pitch)
    yaw = float(car.physics.rotation.yaw)

    facing_x = math.cos(pitch) * math.cos(yaw)
    facing_y = math.cos(pitch) * math.sin(yaw)

    return Vector2(facing_x, facing_y)


class Atba(Bot):
    state_setting = False
    rendering = False
    match_comms = False

    def initialize_agent(self):
        self.logger.info("Initializing agent!")

        self.last_send = 0
        self.controller = flat.ControllerState()
        num_boost_pads = len(self.get_field_info().boost_pads)
        self.logger.info(f"There are {num_boost_pads} boost pads on the field.")

        self.renderer.begin_rendering("custom one-time rendering group")
        self.renderer.draw(
            flat.PolyLine3D(
                [
                    flat.Vector3(1000, 1000, 100),
                    flat.Vector3(1000, -1000, 500),
                    flat.Vector3(-1000, -1000, 1000),
                ],
                self.renderer.yellow,
            )
        )
        self.renderer.end_rendering()

    def handle_match_communication(self, match_comm: flat.MatchComm):
        self.logger.info(f"Received match communication from index {match_comm.index}! {match_comm.display}")

    def get_output(self, packet: flat.GameTickPacket) -> flat.ControllerState:
        if self.rendering:
            self.test_rendering(packet)

        if int(packet.game_info.game_state_type) not in {
            int(flat.GameStateType.Active),
            int(flat.GameStateType.Kickoff),
        }:
            return self.controller

        if self.state_setting:
            self.test_state_setting(packet.ball.physics.velocity)

        if self.match_comms:
            # Only send a message once a second to prevent spam
            if packet.game_info.frame_num - self.last_send >= 120:
                self.send_match_comm(b"", "Hello world!")
                self.last_send = packet.game_info.frame_num

        ball_location = Vector2.from_vector3t(packet.ball.physics.location)

        my_car = packet.players[self.index]
        car_location = Vector2.from_vector3t(my_car.physics.location)
        car_direction = get_car_facing_vector(my_car)
        car_to_ball = ball_location - car_location

        steer_correction_radians = car_direction.correction_to(car_to_ball)

        self.controller.steer = -steer_correction_radians
        self.controller.throttle = 1

        return self.controller

    def test_state_setting(self, ball_velocity: flat.Vector3):
        game_state = flat.DesiredGameState(
            flat.DesiredBallState(
                flat.DesiredPhysics(
                    velocity=flat.Vector3Partial(z=ball_velocity.z + 10)
                )
            )
        )
        self.set_game_state(game_state)

    def test_rendering(self, packet: flat.GameTickPacket):
        self.renderer.begin_rendering()
        text = "Hello world!\nI hope I'm centered!"
        self.renderer.draw(
            flat.String3D(
                text,
                packet.players[self.index].physics.location,
                1.5,
                self.renderer.yellow,
                self.renderer.transparent,
                flat.TextHAlign.Center,
            )
        )
        self.renderer.end_rendering()


if __name__ == "__main__":
    Atba().run()
