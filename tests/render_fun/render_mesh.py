from __future__ import annotations

import zipfile
from dataclasses import dataclass

from rlbot import flat
from rlbot.managers import Renderer


class Vector3(flat.Vector3):
    def __mul__(self, other: Vector3):
        return Vector3(self.x * other.x, self.y * other.y, self.z * other.z)

    def __add__(self, other: Vector3):
        return Vector3(self.x + other.x, self.y + other.y, self.z + other.z)


@dataclass
class Polygon:
    vertices: list[Vector3]


@dataclass
class ColoredPolygonGroup:
    name: str
    polygons: list[Polygon]
    color: flat.Color


class ColoredWireframe:
    """
    Parses a .obj file and renders it inside the arena over time.
    To give your mesh the correct colors, you have to make each differently colored part a separate object/group,
    and name them like this: name_HEXVALUE, for example 'white_FFFFFF'
    """

    def __init__(
        self,
        file_path: str,
        scale: Vector3 = Vector3(1, 1, 1),
        position: Vector3 = Vector3(0, 0, 0),
    ):
        self.groups: list[ColoredPolygonGroup] = list()

        self.scale = scale
        self.position = position

        self.polygons_rendered = 0
        self.current_color_group = 0

        file = open(file_path)

        lines = file.readlines()
        vertices: list[Vector3] = list()

        # parse vertices
        for line in lines:
            if line.startswith("v "):
                v = line.split(" ")
                vertex = (
                    Vector3(float(v[3]), float(v[1]), float(v[2])) * scale + position
                )
                vertices.append(vertex)

        for line in lines:
            # parse color groups
            if line.startswith("o "):
                group_name, hex_color = line.split(" ")[1].split("_")
                r, g, b = tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))

                self.groups.append(
                    ColoredPolygonGroup(
                        name=group_name[0],
                        polygons=list(),
                        color=flat.Color(255, r, g, b),
                    )
                )

            # parse polygons
            if line.startswith("f "):
                s = line.split(" ")
                polygon = Polygon(list())

                for face in (
                    s[1:] + s[1:1]
                ):  # to make polyline work, add the first vertex at the end
                    vertex_index = (
                        int(face.split("/")[0]) - 1
                    )  # faces begin at 1, arrays at 0
                    polygon.vertices.append(vertices[vertex_index])

                self.groups[-1].polygons.append(polygon)  # append the most recent group

    def render(self, renderer: Renderer):
        for _ in range(10):
            if self.current_color_group < len(self.groups):
                unique_group_name = str(self.polygons_rendered) + str(
                    self.current_color_group
                )
                renderer.begin_rendering(unique_group_name)

                group: ColoredPolygonGroup = self.groups[self.current_color_group]

                for _ in range(50):
                    if self.polygons_rendered < len(group.polygons):
                        renderer.draw_polyline_3d(
                            group.polygons[self.polygons_rendered].vertices,
                            group.color,
                        )

                        self.polygons_rendered += 1
                    else:
                        self.polygons_rendered = 0
                        self.current_color_group += 1
                        break
                renderer.end_rendering()


def unzip_and_build_obj() -> ColoredWireframe:
    import os

    dirpath = os.path.dirname(os.path.realpath(__file__))
    with zipfile.ZipFile(dirpath + "/nothing.zip", "r") as zip_ref:
        zip_ref.extractall(dirpath)
    return ColoredWireframe(
        dirpath + "/zerotwo.obj", Vector3(70, 70, 70), Vector3(-3500, 0, 0)
    )
