from __future__ import annotations

import math

from rlbot import flat
from rlbot.managers import Hivemind


class Vector2:
    def __init__(self, x: float | flat.Vector3 = 0, y: float = 0, z: float = 0):
        match x:
            case flat.Vector3(v_x, v_y, _):
                self.x = v_x
                self.y = v_y
            case _:
                self.x = x
                self.y = y

    def __add__(self, val) -> Vector2:
        return Vector2(self.x + val.x, self.y + val.y)

    def __sub__(self, val) -> Vector2:
        return Vector2(self.x - val.x, self.y - val.y)

    def correction_to(self, ideal: Vector2) -> float:
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


def get_car_facing_vector(car: flat.PlayerInfo) -> Vector2:
    pitch = float(car.physics.rotation.pitch)
    yaw = float(car.physics.rotation.yaw)

    facing_x = math.cos(pitch) * math.cos(yaw)
    facing_y = math.cos(pitch) * math.sin(yaw)

    return Vector2(facing_x, facing_y)


class Hives(Hivemind):
    controllers: dict[int, flat.ControllerState] = {}

    def get_outputs(
        self, packet: flat.GameTickPacket
    ) -> dict[int, flat.ControllerState]:
        if (
            packet.game_info.game_state_type
            not in {
                flat.GameStateType.Active,
                flat.GameStateType.Kickoff,
            }
            or len(packet.balls) == 0
        ):
            return self.controllers

        ball_location = Vector2(packet.balls[0].physics.location)

        self.controllers.clear()
        for i in self.indicies:
            self.controllers[i] = flat.ControllerState()

            my_car = packet.players[i]
            car_location = Vector2(my_car.physics.location)
            car_direction = get_car_facing_vector(my_car)
            car_to_ball = ball_location - car_location

            steer_correction_radians = car_direction.correction_to(car_to_ball)

            self.controllers[i].steer = -steer_correction_radians
            self.controllers[i].throttle = 1
            self.controllers[i].boost = True

        return self.controllers


if __name__ == "__main__":
    Hives().run()
