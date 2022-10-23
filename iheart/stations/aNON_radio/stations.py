import vlc

from ..base import Station
from iheart.colors import Colors


class aNONradio(Station):

	def __init__(self):
		station_dict = {
			'id': 'aNON',
			'user_id': 'aNON',
			'name': 'aNONradio.net',
			'mrl': "http://anonradio.net:8000/anonradio"
		}
		super().__init__(station_dict)

	def __str__(self):
		player = self.get_player()
		if player.plr:
			media = player.plr.get_media()
			if not media.is_parsed():
				media.parse()
			desc = '"{}" on "{}"'.format(
				Colors.colorize(str(media.get_meta(vlc.Meta.NowPlaying)), Colors.YELLOW, bold=True),
				Colors.colorize(str(media.get_meta(vlc.Meta.Title)), Colors.GREEN, bold=True),
			)
		else:
			desc = Colors.colorize(self.mrl, Colors.BLUE, bold=True)
		decor = Colors.colorize("**", Colors.RED)
		return "{} {}: {} {}".format(
			decor,
			Colors.colorize(self.name, Colors.CYAN, bold=True),
			desc,
			decor
		)

	def forward(self):
		# disable forwarding
		pass

	def rewind(self):
		# disable rewinding
		pass
