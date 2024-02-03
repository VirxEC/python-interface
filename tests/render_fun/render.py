from render_mesh import *

from rlbot.managers.script import ScriptManager


class RenderFun(ScriptManager):
    def __init__(self):
        self.zero_two = unzip_and_build_obj()

    def handle_packet(self, _):
        self.zero_two.render(self.renderer)


if __name__ == "__main__":
    RenderFun().run()
