from ..base import LiveStation
from .client import ir_search

from iheart.colors import Colors


class InternetRadio(LiveStation):

    def __init__(self):
        station_dicts = ir_search("rock", sortby="featured")
        print("Options not implemented yet. Here's what it looks like for search term 'rock'")
        for i, d in enumerate(station_dicts):
            print(f"\t{i}) {d['name']} ({d['current_track']}) [{d['listeners']} listeners]")
        print("selecting 0")
        print("tuning in..")
        super().__init__(station_dicts[0])

    def info(self):
        return self.get_dict()

    def _get_descr(self):
        if self.now_playing is not None:
            return '"{}"'.format(
                Colors.colorize(str(self.now_playing), Colors.YELLOW, bold=True),
            )
        data = self.get_dict()
        return "({}) {}".format(
            Colors.colorize(str(data['current_track']), Colors.BLUE, bold=True),
            Colors.colorize(f"[{data['listeners']} listeners]", Colors.GRAY),
        )
