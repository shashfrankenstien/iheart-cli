import sys
import time
from datetime import timedelta

from iheart.colors import Colors
from iheart.player import VLCPlayer

PRINT_PLAYING_URL = False



class Station(object):
	'''
	This class implements a simple station such as live radio
	- it has just one mrl / track which is expected to keep playing
	'''
	CURRENT_PLAYING_MRL = ''

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
			if self.mrl != self.CURRENT_PLAYING_MRL:
				# only print now playing name if the new mrl is different
				if PRINT_PLAYING_URL: sys.stdout.write(Colors.colorize(self.mrl, Colors.GRAY) + "\n\r")

			player = self.get_player()
			self.show_time()
			player.play()
			# media url might take a bit to load. while loading, is_playing returns False.
			# - sleeping a bit to allow time for the player to load the url and start playing
			# - time this out at 10 seconds
			sys.stdout.write("\r\t+..:..\r")
			st = time.time()
			while not player.is_playing() and time.time()-st < 10:
				time.sleep(0.5)
			if not player.is_playing():
				raise TimeoutError("could not play {}".format(self.mrl))
			self.CURRENT_PLAYING_MRL = self.mrl # register class level current playing mrl


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
		return {'mrl': self.mrl, 'id': self.id, 'name': self.name}

	def _print_time(self, event):
		if event.elapsed is not None:
			elapsed = int(event.elapsed)
			hhmmss = str(timedelta(seconds=elapsed))
			countdown = f"\t+{hhmmss}\r"
			sys.stdout.write(Colors.colorize(countdown, Colors.WHITE, bold=True))

	def show_time(self, show=True):
		if show:
			self.get_player().register_event(VLCPlayer.POSITION_CHANGED, self._print_time)
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

		self.duration = content.get('duration') or 0
		minutes = self.duration // 60
		seconds = self.duration % 60
		self.duration_str = f"{minutes}:{seconds:02d}"
		self.duration_str_padded = f"{minutes:02d}:{seconds:02d}"

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
		s += Colors.colorize(f" ({self.duration_str})", Colors.GRAY) # add song duration
		return s

	def __repr__(self):
		return str(self)




class TrackListStation(Station):
	'''
	This Station subclass implements a more advanced station which contains multiple tracks
	- it has multiple Track objects which plays one after the other
	- this is controlled by overriding self.iter_tracks() [required]
	'''
	def __init__(self, station_dict):
		super().__init__(station_dict=station_dict)

		self.current_track = None
		self.repeat = False
		self._on_complete_cb = lambda _:None

	def iter_tracks(self):
		raise NotImplementedError("'iter_tracks' should be overridden in a subclass")

	def get_current_track(self):
		return self.current_track

	def toggle_repeat(self):
		self.repeat = not self.repeat

	def info(self):
		try:
			return self.current_track.get_dict()
		except Exception as e:
			print(e)

	def _print_time(self, event): # overridden
		if self.current_track is not None and event.elapsed is not None:
			remaining = int(self.current_track.duration - event.elapsed)
			m = remaining // 60
			s = (remaining % 60)
			countdown = f"\t-{m:02d}:{s:02d}/{self.current_track.duration_str_padded}\r"
			sys.stdout.write(Colors.colorize(countdown, Colors.WHITE, bold=True))

	def _play_next(self, track_generator):
		if self.repeat == False:
			# go to the next track only if not in repeat mode
			self.current_track = next(track_generator)
			self.mrl = self.current_track.mrl

		if self.mrl != self.CURRENT_PLAYING_MRL:
			sys.stdout.write(Colors.colorize("( Now Playing ) ", Colors.GRAY, bold=True) + str(self.current_track) + "\n\r")
		self._on_complete_cb = lambda _: self._play_next(track_generator=track_generator)
		player = self.get_player()
		player.stop()
		player.register_event(player.END_REACHED, self._on_complete_cb)
		super().play()

	def play(self):
		self._play_next(track_generator=self.iter_tracks())

	def forward(self):
		player = self.get_player()
		player.stop() # calling .stop() is not required here, but it makes sense and doesn't hurt
		self._on_complete_cb(None)
