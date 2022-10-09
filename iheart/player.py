import os, sys
import vlc
import time
from datetime import timedelta
import logging
import traceback

if __name__=='__main__':
	# setup imports to be able to run test functions at the end of this file
	from colors import Colors # pylint: disable=import-error
	import client
else:
	from .colors import Colors
	from . import client



# Silent install VLC on windows
# certutil.exe -urlcache -split -f "https://get.videolan.org/vlc/3.0.11/win32/vlc-3.0.11-win32.exe" "vlc-3.0.11-win32.exe"
# vlc-3.0.11-win32.exe /L=1033 /S



CWD = os.path.dirname(os.path.realpath(__file__))
DEFAULT_UUID_STORE = os.path.join(CWD, "iheart.uuid")

PRINT_PLAYING_URL = False

VLC_INSTANCE_FLAGS = "--network-caching=50000 --adaptive-use-access"
if sys.platform.startswith('linux'):
	VLC_INSTANCE_FLAGS += " --aout alsa"


def vlc_is_installed() -> bool:
	try:
		i = vlc.Instance(VLC_INSTANCE_FLAGS) # Create a VLC instance
		i.release()
		return True
	except NameError:
		return False


# **************************************************************************************
# ********************************** Player Classes ************************************
# **************************************************************************************


class VLCPlayer(object):
	'''https://www.olivieraubert.net/vlc/python-ctypes/doc/'''

	POSITION_CHANGED = vlc.EventType.MediaPlayerPositionChanged
	END_REACHED = vlc.EventType.MediaPlayerEndReached
	_PLAYER = None

	def __init__(self, mrl):
		self.mrl = mrl
		self.inst = None
		self.plr = None
		self.list_player = False
		self._paused = False
		self._manager = None
		self._events_registry = {}

		self._play_start_time = None
		self._paused_at = None
		self._total_paused_time = 0

	@classmethod
	def get_player(cls, mrl):
		if cls._PLAYER is None:
			cls._PLAYER = cls(mrl)
		elif mrl!=cls._PLAYER.mrl:
			cls._PLAYER.stop()
			cls._PLAYER = cls(mrl)
		return cls._PLAYER

	def get_internal_player(self):
		if self.list_player:
			return self.plr.get_media_player()
		else:
			return self.plr

	def register_event(self, event_type, callback):
		def _callback_wrapper(event):
			# add event.elapsed - time since play was called
			if self._play_start_time is not None:
				event.elapsed = time.time() - self._play_start_time - self._total_paused_time
			else:
				event.elapsed = None
			callback(event)
		if self._manager is not None:
			self._manager.event_attach(event_type, _callback_wrapper)
		else:
			self._events_registry[event_type] = _callback_wrapper

	def remove_event(self, event_type):
		if self._manager is not None:
			self._manager.event_detach(event_type)
		if event_type in self._events_registry:
			del self._events_registry[event_type]

	def play(self):
		self.stop()
		self.inst = vlc.Instance(VLC_INSTANCE_FLAGS) # Create a VLC instance
		self.inst.log_unset()
		ext = (self.mrl.rpartition(".")[2])[:3]
		if ext in ['pls', 'm3u']:
			media_list = self.inst.media_list_new([self.mrl])
			self.plr = self.inst.media_list_player_new()
			self.plr.set_media_list(media_list)
			self.list_player = True
			# print("playing playlist>")
		else:
			media = self.inst.media_new(self.mrl)
			self.plr = self.inst.media_player_new()
			self.plr.set_media(media)
			self.list_player = False
			# print("playing>")

		self._play_start_time = time.time()
		self._manager = self.get_internal_player().event_manager()
		# apply cached events that were registered before _manager was created
		for evt, cb in self._events_registry.items():
			self.register_event(evt, cb)
		self._events_registry = {}
		self.plr.play()

	def is_playing(self):
		return self.plr is not None and self.plr.is_playing()

	def is_paused(self):
		return self._paused

	def stop(self):
		if self.plr is not None:
			if not self.plr.get_state() in (vlc.State.Ended, vlc.State.Stopped):
				self.plr.stop()
			self.plr.release()
			self.plr = None
		if self.inst is not None:
			self.inst.release()
			self.inst = None
		self._manager = None
		self._play_start_time = None
		self._paused_at = None
		self._total_paused_time = 0

	def forward(self):
		"""Go forward 10 secs"""
		player = self.get_internal_player()
		player.set_time(player.get_time() + 10000)

	def rewind(self):
		"""Go back 10 secs"""
		player = self.get_internal_player()
		player.set_time(player.get_time() - 10000)

	def toggle_pause(self, pause=True):
		self.plr.set_pause(1 if pause else 0)
		self._paused = pause
		if pause is True:
			self._paused_at = time.time()
		elif self._paused_at is not None:
			self._total_paused_time += time.time() - self._paused_at
		time.sleep(0.1)
		return self.is_playing()
		# return self.plr.get_state()



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
		decor = Colors.colorize("**", Colors.RED)
		return "{} {}: {} ({}) {}".format(
			decor,
			self.__class__.__name__,
			Colors.colorize(self.name, Colors.CYAN, bold=True),
			Colors.colorize(self.mrl, Colors.BLUE, bold=True),
			decor
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
			sys.stdout.write(Colors.colorize(countdown, Colors.WHITE, bold=True))

	def show_time(self, show=True):
		if show:
			self.get_player().register_event(VLCPlayer.POSITION_CHANGED, self._print_elapsed_time)
		else:
			self.get_player().remove_event(VLCPlayer.POSITION_CHANGED)



class LiveStation(Station):
	def __init__(self, station_dict):
		super().__init__(station_dict=station_dict)
		self.__dict = station_dict

		self.description = (self.__dict.get('description') or '').strip()
		self.callLetters = self.__dict.get('callLetters')
		self.frequency = self.__dict.get('frequency')
		self.imageUrl = self.__dict.get('imageUrl')

		self.search_score = self.__dict.get('score')

	def get_dict(self):
		return self.__dict

	def __str__(self):
		decor = Colors.colorize("**", Colors.RED)
		return "{} {}: {} ({}) {}".format(
			decor,
			self.__class__.__name__,
			Colors.colorize(self.name, Colors.CYAN, bold=True),
			Colors.colorize(self.description, Colors.BLUE, bold=True),
			decor
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
		print('Radio: "{}" - "{}" at "{}" {}'.format(
			Colors.colorize(self.name, Colors.YELLOW, bold=True),
			Colors.colorize(self.description, Colors.BLUE, bold=True),
			Colors.colorize(str(self.frequency)+"MHz", Colors.GREEN, bold=True),
			Colors.colorize("- "+self.mrl, Colors.GRAY, bold=False) if PRINT_PLAYING_URL else ''
		))
		player = self.get_player()
		player.play()

	def toggle_pause(self, pause=True):
		if pause and self.is_playing():
			self.stop()
		elif not self.is_playing():
			self.play()

	def is_paused(self):
		return self.is_playing()

	def info(self):
		try:
			return client.iget_live_meta(self.id)
		except Exception as e:
			print(e)




class Track(object):
	# store a class level current playing MRL.
	# - check against this to identify if track is being repeated
	CURRENT_PLAYING_MRL = ''

	def __init__(self, track_dict):
		if 'streamUrl' not in track_dict:
			raise Exception("stream not found")
		self.__dict = track_dict
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
		return self.__dict

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



class ArtistStation(Station):
	def __init__(self, artist_dict):
		super().__init__(station_dict=artist_dict)
		self.__dict = artist_dict
		self.imageUrl = self.__dict.get('image')

		self.search_score = self.__dict.get('score')
		self.rank = self.__dict.get('rank')

		self.station_hash = None
		self.current_track = None

		self.repeat = False

	def get_dict(self):
		return self.__dict

	def __str__(self):
		decor = Colors.colorize("**", Colors.RED)
		return "{} {}: {} ({}) {}".format(
			decor,
			self.__class__.__name__,
			Colors.colorize(self.name, Colors.CYAN, bold=True),
			Colors.colorize(str(self.id), Colors.PINK, bold=True),
			decor
		)

	def iter_tracks(self):
		while True:
			try:
				station_data = client.iget_artist_station(self.user_id, self.id)
				self.station_hash = station_data['id']
				for trk_dict in client.iget_artist_streams(self.station_hash):
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
		self.__dict = {
			'id': track_dict['artistId'],
			'name': track_dict['title'] + " - " + track_dict['artistName'],
			'image': track_dict['image'],
			'user_id': track_dict['user_id'],
		}
		super().__init__(artist_dict=self.__dict)






class iHeart(object):

	TRACKS = 'tracks'
	ARTISTS = 'artists'
	STATIONS = 'stations'

	# # other choices - Not implemented yet
	# PLAYLISTS = 'playlists'
	# ALBUMS = 'albums'
	# PODCASTS = "podcasts"
	# FEATURED_STATIONS = "featuredStations"
	# TALKSHOWS = "talkShows"
	# TALKTHEMES = "talkThemes"

	def __init__(self, uuid_store=DEFAULT_UUID_STORE, print_url=False):
		self.user = client.ilogin(uuid_store=uuid_store)
		self.user_id = self.user['profileId']
		global PRINT_PLAYING_URL
		PRINT_PLAYING_URL = print_url

	def search(self, keyword, category=None, startIndex=0):
		if category is None: category = self.ARTISTS
		search_res = client.isearch(keyword, startIndex=startIndex)

		if category==self.STATIONS:
			station_class = LiveStation
		elif category==self.ARTISTS:
			station_class = ArtistStation
		elif category==self.TRACKS:
			station_class = SongStation
		else:
			# return search_res['results'][category]
			raise NotImplementedError("'{}' not implemented yet")

		out = []
		for result in search_res['results'][category]:
			result['user_id'] = self.user_id
			out.append(station_class(result))
		return out



if __name__ == "__main__":
	import json
	printjson = lambda j: print(json.dumps(j, indent=4))


	def test_player():
		url = 'http://custom-hls.iheart.com/bell-ingestion-pipeline-production-umg/encodes/Dec18/121218/full/00602537937011_20181206002655653/00602537937011_T55_audtrk.m4a.m3u8?null'
		player = VLCPlayer.get_player(url)
		player.play()
		print('''<Track: "Bad Medicine" by "Bon Jovi" on "Bon Jovi">''')
		time.sleep(25)
		player.stop()


	def test_stations():
		radio = iHeart()
		res = radio.search("Classic Rock", category=iHeart.STATIONS)
		for station in res[:2]:
			station.play()
			time.sleep(10)
			station.stop()
			time.sleep(2)


	def test_artist_radio():
		artist_keyword = "Queen" # = input("Search for artist: ")
		radio = iHeart()
		artist = radio.search(artist_keyword, category=iHeart.ARTISTS)[0]
		print(artist)
		printjson(artist.get_dict())
		# artist.play()
		# time.sleep(10)
		# artist.stop()
		# printjson({'a': artist.get_current_track().get_dict()})

	def test_track_search():
		track_name = "wild world"
		radio = iHeart()
		res1 = radio.search(track_name, category=iHeart.TRACKS)[0]
		print(res1)
		printjson(res1.get_dict())
		# res1.play()
		# time.sleep(10)
		# res1.stop()
		# printjson({'a': res1.get_current_track().get_dict()})

		# printjson(iget_track_info(res1['id']))


	test_player()
	test_track_search()
	test_artist_radio()

