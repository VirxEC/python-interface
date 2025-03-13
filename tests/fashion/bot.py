import csv
from random import choice, randint

from rlbot import flat
from rlbot.config import load_player_loadout
from rlbot.managers import Bot


class Fashion(Bot):
    standard_loadout: flat.PlayerLoadout
    last_tick = 0
    items: dict[str, list[int]] = {}

    def initialize(self):
        with open("./items.csv") as f:
            reader = csv.reader(f)
            for row in reader:
                if row[1] not in self.items:
                    self.items[row[1]] = []

                self.items[row[1]].append(int(row[0]))

        self.standard_loadout = load_player_loadout("../necto/loadout.toml", self.team)
        self.set_loadout(self.standard_loadout)

    def get_output(self, packet: flat.GamePacket) -> flat.ControllerState:
        if packet.match_info.match_phase != flat.MatchPhase.Active:
            return flat.ControllerState()

        if packet.match_info.frame_num - self.last_tick >= 2 * 120:
            loadout = flat.PlayerLoadout(
                team_color_id=randint(0, 69),
                custom_color_id=randint(0, 104),
                car_id=choice(self.items["Body"]),
                wheels_id=choice(self.items["Wheels"]),
                decal_id=0,
                boost_id=choice(self.items["Boost"]),
                antenna_id=choice(self.items["Antenna"]),
                hat_id=choice(self.items["Hat"]),
                paint_finish_id=choice(self.items["PaintFinish"]),
                loadout_paint=flat.LoadoutPaint(
                    randint(0, 18),
                    randint(0, 18),
                    randint(0, 18),
                    randint(0, 18),
                    randint(0, 18),
                    randint(0, 18),
                    randint(0, 18),
                    randint(0, 18),
                ),
            )

            self.logger.info(f"State setting new loadout")
            self.set_loadout(loadout)
            self.last_tick = packet.match_info.frame_num

        return flat.ControllerState(throttle=1, steer=1)


if __name__ == "__main__":
    Fashion("testing/fashion").run()
