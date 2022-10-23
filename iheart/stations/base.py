import sys
import time
from datetime import timedelta

from iheart.colors import Colors
from iheart.player import VLCPlayer

PRINT_PLAYING_URL = False



class Station(object):

	def __init__(self, station_dict):
		self._dict = station_dict
		if 'id' not in self._dict:
			raise Exception("station id not found")
		self.id = self._dict['id']
		self.user_id = self._dict.get('user_id')
		self.mrl = self._dict.get('mrl', None)
		self.name = self._dict.get('name') or self.__class__.__name__

	def get_dict(self):
		return self._dict

	def __str__(self):
		decor = Colors.colorize("**", Colors.RED)
		return "{} {}: {} ({}) {} {}".format(
			decor,
			self.__class__.__name__,
			Colors.colorize(self.name, Colors.CYAN, bold=True),
			Colors.colorize(str(self.id), Colors.BLUE, bold=True),
			decor,
			Colors.colorize("- "+str(self.mrl), Colors.GRAY, bold=False) if PRINT_PLAYING_URL else '',
		)

	def __repr__(self):
		return str(self)

	def get_player(self):
		return VLCPlayer.get_player(self.mrl)

	def play(self):
		if self.mrl is not None:
			player = self.get_player()
			player.play()
			# media url might take a bit to load. while loading, is_playing returns False.
			# - sleeping a bit to allow time for the player to load the url and start playing
			# - time this out at 10 seconds
			sys.stdout.write("\t+..:..\r")
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
			self.get_player().rewind()

	def info(self):
		return {'mrl': self.mrl, 'id': self.id}

	def _print_elapsed_time(self, event):
		if event.elapsed is not None:
			elapsed = int(event.elapsed)
			hhmmss = str(timedelta(seconds=elapsed))
			countdown = f"\t+{hhmmss}\r"
			sys.stdout.write(Colors.colorize(countdown, Colors.WHITE, bold=True))

	def show_time(self, show=True):
		if show:
			self.get_player().register_event(VLCPlayer.POSITION_CHANGED, self._print_elapsed_time)
		else:
			self.get_player().remove_event(VLCPlayer.POSITION_CHANGED)






class Track(object):
	# store a class level current playing MRL.
	# - check against this to identify if track is being repeated
	CURRENT_PLAYING_MRL = ''

	def __init__(self, track_dict):
		if 'streamUrl' not in track_dict:
			raise Exception("stream not found")
		self._dict = track_dict
		self.mrl = track_dict['streamUrl'].replace("https", 'http')

		content = track_dict['content']
		self.id = content['id']
		self.name = content.get('title')
		self.version = content.get('version')
		self.artist = content.get('artistName')
		self.artist_id = content.get('artistId')
		self.album = content.get('albumName')
		self.album_id = content.get('albumId')
		self.lyrics_id = content.get('lyricsId')
		self.imageUrl = content.get('imagePath')

		self.length = content.get('duration')
		self.minutes = self.length // 60
		self.seconds = self.length % 60

		self._on_complete_cb = lambda event:None
		self.__show_time = True

	def get_dict(self):
		return self._dict

	def __str__(self):
		s = '''Track: "{}" by "{}" on "{}"'''.format(
			Colors.colorize(self.name, Colors.YELLOW, bold=True),
			Colors.colorize(self.artist, Colors.LIGHT_BLUE, bold=True),
			Colors.colorize(self.album, Colors.GREEN, bold=True),
		)
		if self.version:
			s += " [" + Colors.colorize(self.version, Colors.RED, bold=True) + "]"
		s += Colors.colorize(f" ({self.minutes}:{self.seconds:02d})", Colors.GRAY) # add song duration
		return s

	def __repr__(self):
		return str(self)

	def show_time(self, show=True):
		self.__show_time = show

	def _print_remaining_duration(self, event):
		if self.__show_time:
			remaining = int(self.length - event.elapsed)
			m = remaining // 60
			s = (remaining % 60)
			countdown = f"\t-{m:02d}:{s:02d}/{self.minutes:02d}:{self.seconds:02d}\r"
			sys.stdout.write(Colors.colorize(countdown, Colors.WHITE, bold=True))

	def play(self, on_complete):
		self._on_complete_cb = on_complete
		if self.mrl != self.CURRENT_PLAYING_MRL:
			# only print now playing track name if the new track is different
			if PRINT_PLAYING_URL: sys.stdout.write(Colors.colorize(self.mrl, Colors.GRAY) + "\n\r")
			sys.stdout.write(Colors.colorize("( Now Playing ) ", Colors.GRAY, bold=True) + str(self) + "\n\r")
		player = VLCPlayer.get_player(self.mrl)
		player.stop()
		player.register_event(player.END_REACHED, self._on_complete_cb)
		player.register_event(player.POSITION_CHANGED, self._print_remaining_duration)
		self.CURRENT_PLAYING_MRL = self.mrl # register class level current playing mrl
		player.play()

	def force_end(self):
		player = VLCPlayer.get_player(self.mrl)
		player.stop() # calling .stop() is not required here, but it makes sense and doesn't hurt
		self._on_complete_cb(None)

