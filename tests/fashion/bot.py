from __future__ import annotations

from rlbot import flat
from rlbot.config import load_player_loadout
from rlbot.managers import Bot


class Fashion(Bot):
    def initialize(self):
        self.set_loadout(load_player_loadout("../necto/loadout.toml", self.team))

    def get_output(self, packet: flat.GamePacket) -> flat.ControllerState:
        return flat.ControllerState()


if __name__ == "__main__":
    Fashion("testing/fashion").run()
