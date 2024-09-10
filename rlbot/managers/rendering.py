from typing import Callable, Optional, Sequence

from rlbot import flat
from rlbot.interface import SocketRelay
from rlbot.utils.logging import get_logger

MAX_INT = 2147483647 // 2
DEFAULT_GROUP_ID = "default"


def _get_anchor(
    anchor: flat.RenderAnchor | flat.BallAnchor | flat.CarAnchor | flat.Vector3,
):
    match anchor:
        case flat.BallAnchor() | flat.CarAnchor():
            return flat.RenderAnchor(relative=anchor)
        case flat.Vector3():
            return flat.RenderAnchor(anchor)
        case _:
            return anchor


class Renderer:
    transparent = flat.Color()
    black = flat.Color(255)
    white = flat.Color(255, 255, 255, 255)
    grey = gray = flat.Color(255, 128, 128, 128)
    blue = flat.Color(255, 0, 0, 255)
    red = flat.Color(255, 255, 0, 0)
    green = flat.Color(255, 0, 128, 0)
    lime = flat.Color(255, 0, 255, 0)
    yellow = flat.Color(255, 255, 255, 0)
    orange = flat.Color(255, 225, 128, 0)
    cyan = flat.Color(255, 0, 255, 255)
    pink = flat.Color(255, 255, 0, 255)
    purple = flat.Color(255, 128, 0, 128)
    teal = flat.Color(255, 0, 128, 128)

    _logger = get_logger("renderer")

    _used_group_ids: set[int] = set()
    _group_id: Optional[int] = None
    _current_renders: list[flat.RenderMessage] = []

    def __init__(self, game_interface: SocketRelay):
        self._render_group: Callable[[flat.RenderGroup], None] = (
            game_interface.send_render_group
        )

        self._remove_render_group: Callable[[int], None] = (
            game_interface.remove_render_group
        )

    @staticmethod
    def create_color(red: int, green: int, blue: int, alpha: int = 255):
        return flat.Color(alpha, red, green, blue)

    @staticmethod
    def team_color(team: int, alt_color: bool = False):
        if team == 0:
            return Renderer.cyan if alt_color else Renderer.blue
        elif team == 1:
            return Renderer.red if alt_color else Renderer.orange

        return Renderer.gray if alt_color else Renderer.white

    @staticmethod
    def _get_group_id(group_id: str) -> int:
        return hash(str(group_id).encode("utf-8")) % MAX_INT

    def begin_rendering(self, group_id: str = DEFAULT_GROUP_ID):
        """
        Begins a new render group. All renders added after this call will be part of this group.
        """
        if self._group_id is not None:
            self._logger.error(
                "begin_rendering was called twice without end_rendering."
            )
            return

        self._group_id = Renderer._get_group_id(group_id)
        self._used_group_ids.add(self._group_id)

    def end_rendering(self):
        if self._group_id is None:
            self._logger.error(
                "end_rendering was called without begin_rendering first."
            )
            return

        self._render_group(flat.RenderGroup(self._current_renders, self._group_id))
        self._current_renders.clear()
        self._group_id = None

    def clear_render_group(self, group_id: str = DEFAULT_GROUP_ID):
        group_id_hash = Renderer._get_group_id(group_id)
        self._remove_render_group(group_id_hash)
        self._used_group_ids.discard(group_id_hash)

    def clear_all_render_groups(self):
        """
        Clears all render groups which have been drawn to using `begin_rendering(group_id)`.
        Note: This does not clear render groups created by other bots.
        """
        for group_id in self._used_group_ids:
            self._remove_render_group(group_id)
        self._used_group_ids.clear()

    def is_rendering(self):
        """
        Returns True if `begin_rendering` has been called without a corresponding `end_rendering`.
        """
        return self._group_id is not None

    def _draw(
        self, render: flat.String2D | flat.String3D | flat.Line3D | flat.PolyLine3D
    ):
        self._current_renders.append(flat.RenderMessage(render))

    def draw_line_3d(
        self,
        start: flat.RenderAnchor | flat.BallAnchor | flat.CarAnchor | flat.Vector3,
        end: flat.RenderAnchor | flat.BallAnchor | flat.CarAnchor | flat.Vector3,
        color: flat.Color,
    ):
        self._draw(flat.Line3D(_get_anchor(start), _get_anchor(end), color))

    def draw_polyline_3d(
        self,
        points: Sequence[flat.Vector3],
        color: flat.Color,
    ):
        self._draw(flat.PolyLine3D(points, color))

    def draw_string_3d(
        self,
        text: str,
        anchor: flat.RenderAnchor | flat.BallAnchor | flat.CarAnchor | flat.Vector3,
        scale: float,
        foreground: flat.Color,
        background: flat.Color = flat.Color(),
        h_align: flat.TextHAlign = flat.TextHAlign.Left,
        v_align: flat.TextVAlign = flat.TextVAlign.Top,
    ):
        self._draw(
            flat.String3D(
                text,
                _get_anchor(anchor),
                scale,
                foreground,
                background,
                h_align,
                v_align,
            )
        )

    def draw_string_2d(
        self,
        text: str,
        x: float,
        y: float,
        scale: float,
        foreground: flat.Color,
        background: flat.Color = flat.Color(),
        h_align: flat.TextHAlign = flat.TextHAlign.Left,
        v_align: flat.TextVAlign = flat.TextVAlign.Top,
    ):
        self._draw(
            flat.String2D(
                text,
                x,
                y,
                scale,
                foreground,
                background,
                h_align,
                v_align,
            )
        )
