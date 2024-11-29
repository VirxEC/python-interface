from render_mesh import *

from rlbot.managers import Script


class RenderFun(Script):
    zero_two = unzip_and_build_obj()

    def handle_packet(self, _):
        self.zero_two.render(self.renderer)


if __name__ == "__main__":
    RenderFun().run(wants_match_communications=False, wants_ball_predictions=False)
