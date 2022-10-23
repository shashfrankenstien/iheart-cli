
import time

from . import client
from ..base import Station, Track, PRINT_PLAYING_URL
from iheart.colors import Colors



class LiveStation(Station):
	def __init__(self, station_dict):
		super().__init__(station_dict=station_dict)
		self.description = (self._dict.get('description') or '').strip()
		self.callLetters = self._dict.get('callLetters')
		self.frequency = self._dict.get('frequency')
		self.imageUrl = self._dict.get('imageUrl')

		self.search_score = self._dict.get('score')

	def __str__(self):
		decor = Colors.colorize("**", Colors.RED)
		return "{} {}: {} ({} at {}) {} {}".format(
			decor,
			self.__class__.__name__,
			Colors.colorize(self.name, Colors.CYAN, bold=True),
			Colors.colorize(self.description, Colors.BLUE, bold=True),
			Colors.colorize(str(self.frequency)+"MHz", Colors.GREEN, bold=True),
			decor,
			Colors.colorize("- "+self.mrl, Colors.GRAY, bold=False) if PRINT_PLAYING_URL else '',
		)

	def _parse_stream(self):
		self.streams = client.iget_station_streams(self.id)
		if 'hls_stream' in self.streams:
			self.mrl = self.streams['hls_stream'].strip()
		elif 'secure_shoutcast_stream' in self.streams:
			self.mrl = self.streams['secure_shoutcast_stream'].strip()
		elif 'secure_pls_stream' in self.streams:
			self.mrl = self.streams['secure_pls_stream'].strip()
		else:
			try:
				self.mrl = list(self.streams.values())[0].strip()
			except Exception as e:
				print(e)

	def play(self):
		self._parse_stream()
		if self.mrl is None:
			raise Exception("Stream not available for {}".format(self))
		super().play()

	def toggle_pause(self, pause=True):
		if pause and self.is_playing():
			self.stop()
		elif not self.is_playing():
			self.play()

	def info(self):
		try:
			return client.iget_live_meta(self.id)
		except Exception as e:
			print(e)




class ArtistStation(Station):
	def __init__(self, artist_dict):
		super().__init__(station_dict=artist_dict)
		self.imageUrl = self._dict.get('image')
		self.search_score = self._dict.get('score')
		self.rank = self._dict.get('rank')

		self.current_track = None
		self.repeat = False

	def iter_tracks(self):
		while True:
			try:
				station_data = client.iget_artist_station(self.user_id, self.id)
				for trk_dict in client.iget_artist_streams(station_data['id']):
					yield Track(trk_dict)
			except Exception as e:
				print(e)
				time.sleep(0.5)

	def get_current_track(self):
		return self.current_track

	def show_time(self, show=True):
		self.current_track.show_time(show)

	def _play_next(self, track_generator):
		if self.repeat == False:
			# go to the next track only if not in repeat mode
			self.current_track = next(track_generator)
			self.mrl = self.current_track.mrl
		_next_player = lambda _: self._play_next(track_generator=track_generator)
		self.current_track.play(on_complete=_next_player)

	def play(self):
		self._play_next(track_generator=self.iter_tracks())

	def info(self):
		try:
			return self.current_track.get_dict()
		except Exception as e:
			print(e)

	def forward(self):
		self.current_track.force_end()

	def toggle_repeat(self):
		self.repeat = not self.repeat


class SongStation(ArtistStation):

	def __init__(self, track_dict):
		# artist = iget_artist_profile(track_dict['artistId'])
		artist_dict = {
			'id': track_dict['artistId'],
			'name': track_dict['title'] + " - " + track_dict['artistName'],
			'image': track_dict['image'],
			'user_id': track_dict['user_id'],
		}
		super().__init__(artist_dict=artist_dict)



