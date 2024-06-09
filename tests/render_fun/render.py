from render_mesh import *

from rlbot.managers import Script


class RenderFun(Script):
    def __init__(self):
        super().__init__("RenderFun")

        self.zero_two = unzip_and_build_obj()

    def run(self):
        self._game_interface.connect_and_run(False, False, False)
        del self._game_interface

    def handle_packet(self, _):
        self.zero_two.render(self.renderer)


if __name__ == "__main__":
    RenderFun().run()
