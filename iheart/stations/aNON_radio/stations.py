from ..base import LiveStation
from iheart.colors import Colors


class aNONradio(LiveStation):

	def __init__(self):
		station_dict = {
			'id': 'aNON',
			'user_id': 'aNON',
			'name': 'aNONradio.net',
			'mrl': "http://anonradio.net:8000/anonradio"
		}
		super().__init__(station_dict)

	def _get_descr(self):
		if self.now_playing is not None:
			return '"{}"'.format(
				Colors.colorize(str(self.now_playing), Colors.YELLOW, bold=True),
			)
		return super()._get_descr()
