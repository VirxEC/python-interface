from rlbot import flat
from rlbot.flat import BallAnchor, Vector3, CarAnchor
from rlbot.managers import Script


class RenderFun(Script):
    def __init__(self):
        super().__init__("RenderFun")

        self.needs_render = True
        self.last_state = flat.GameStateType.Inactive

    def handle_packet(self, packet: flat.GameTickPacket):
        if (
            packet.game_info.game_state_type != flat.GameStateType.Replay
            and self.last_state == flat.GameStateType.Replay
        ):
            self.needs_render = True
        self.last_state = packet.game_info.game_state_type

        if self.needs_render:
            self.needs_render = False

            match packet.balls[0].shape.item:
                case flat.SphereShape() | flat.CylinderShape() as shape:
                    radius = shape.diameter / 2
                case flat.BoxShape() as shape:
                    radius = shape.length / 2

            self.do_render(radius)

    def do_render(self, radius: float):
        self.renderer.begin_rendering()

        points = [
            BallAnchor(local=Vector3(radius, radius, radius)),
            BallAnchor(local=Vector3(radius, radius, -radius)),
            BallAnchor(local=Vector3(radius, -radius, -radius)),
            BallAnchor(local=Vector3(radius, -radius, radius)),
            BallAnchor(local=Vector3(-radius, -radius, radius)),
            BallAnchor(local=Vector3(-radius, -radius, -radius)),
            BallAnchor(local=Vector3(-radius, radius, -radius)),
            BallAnchor(local=Vector3(-radius, radius, radius)),
            BallAnchor(local=Vector3(radius, radius, radius)),
        ]

        for i in range(1, len(points)):
            self.renderer.draw_line_3d(points[i - 1], points[i], self.renderer.yellow)

        points = [
            BallAnchor(),
            CarAnchor(0),
            Vector3(),
        ]

        for i in range(1, len(points)):
            self.renderer.draw_line_3d(points[i - 1], points[i], self.renderer.red)

        self.renderer.end_rendering()


if __name__ == "__main__":
    RenderFun().run(False, False)
