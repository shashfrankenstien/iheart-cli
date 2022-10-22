import sys
import time
from datetime import timedelta

# from iheart.colors import colors.Colors
# from iheart.player import player.VLCPlayer, Track, PRINT_PLAYING_URL

from iheart import player, colors


class Station(object):

	def __init__(self, station_dict):
		self.__dict = station_dict
		if 'id' not in self.__dict:
			raise Exception("station id not found")
		self.id = self.__dict['id']
		self.user_id = self.__dict['user_id']
		self.mrl = self.__dict.get('mrl', None)
		self.name = self.__dict.get('name') or self.__class__.__name__

	def get_dict(self):
		return self.__dict

	def __str__(self):
		decor = colors.Colors.colorize("**", colors.Colors.RED)
		return "{} {}: {} ({}) {}".format(
			decor,
			self.__class__.__name__,
			colors.Colors.colorize(self.name, colors.Colors.CYAN, bold=True),
			colors.Colors.colorize(self.mrl, colors.Colors.BLUE, bold=True),
			decor
		)

	def __repr__(self):
		return str(self)

	def get_player(self):
		return player.VLCPlayer.get_player(self.mrl)

	def play(self):
		if self.mrl is not None:
			player = self.get_player()
			player.play()
			# media url might take a bit to load. while loading, is_playing returns False.
			# - sleeping a bit to allow time for the player to load the url and start playing
			# - timeout this wait at 10 seconds
			st = time.time()
			while not player.is_playing() and time.time()-st < 10:
				time.sleep(0.5)
			if not player.is_playing():
				raise TimeoutError("could not play {}".format(self.mrl))


	def toggle_pause(self, pause=True):
		if self.mrl is not None:
			return self.get_player().toggle_pause(pause=pause)

	def stop(self):
		if self.mrl is not None:
			self.get_player().stop()

	def is_playing(self):
		return self.mrl is not None and self.get_player().is_playing()

	def is_paused(self):
		return self.mrl is not None and self.get_player().is_paused()

	def forward(self):
		if self.mrl is not None:
			self.get_player().forward()

	def rewind(self):
		if self.mrl is not None:
			self.get_player().forward()

	def info(self):
		return {'mrl': self.mrl, 'id': self.id}

	def _print_elapsed_time(self, event):
		if event.elapsed is not None:
			elapsed = int(event.elapsed)
			hhmmss = str(timedelta(seconds=elapsed))
			countdown = f"\t+{hhmmss}\r"
			sys.stdout.write(colors.Colors.colorize(countdown, colors.Colors.WHITE, bold=True))

	def show_time(self, show=True):
		if show:
			self.get_player().register_event(player.VLCPlayer.POSITION_CHANGED, self._print_elapsed_time)
		else:
			self.get_player().remove_event(player.VLCPlayer.POSITION_CHANGED)


