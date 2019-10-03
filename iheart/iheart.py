import os, sys
import requests
import uuid
import vlc
import time
import logging
import traceback
import random


# Install VLC on windows
# certutil.exe -urlcache -split -f "https://get.videolan.org/vlc/3.0.8/win32/vlc-3.0.8-win32.exe" "vlc-3.0.8-win32.exe"
# vlc-3.0.8-win32.exe /L=1033 /S


new_user_url = 'https://us.api.iheart.com/api/v1/account/loginOrCreateOauthUser'
markets_url = 'https://us.api.iheart.com/api/v2/content/markets?countryCode=US&limit=1&cache=true&zipCode={zipCode}'
search_url = 'https://us.api.iheart.com/api/v3/search/all'

#stations
station_stream_url = 'https://us.api.iheart.com/api/v2/content/liveStations/{stream_id}'
meta_url = 'https://us.api.iheart.com/api/v3/live-meta/stream/{stream_id}/currentTrackMeta'


artist_url = 'https://us.api.iheart.com/api/v1/catalog/getArtistByArtistId?artistId={artist_id}' #GET
artist_profile_url = 'https://us.api.iheart.com/api/v3/artists/profiles/{artist_id}' #GET
similar_artists_url = 'https://us.api.iheart.com/api/v1/catalog/artist/{artist_id}/getSimilar' #GET
artist_albums_url = 'https://us.api.iheart.com/api/v3/catalog/artist/{artist_id}/albums' #GET

artist_playlist_url = 'https://us.api.iheart.com/api/v2/playlists/{user_id}/ARTIST/{artist_id}' #POST formData = {'contentId':artist_id, 'playedFrom':10}
artist_stream_url = 'https://us.api.iheart.com/api/v2/playback/streams' # Takes steramId in POST params


#NOTE useful track info - No stream available
track_url = 'https://us.api.iheart.com/api/v1/catalog/getTrackByTrackId?trackId={track_id}' #GET
track2_url = 'https://us.api.iheart.com/api/v3/catalog/tracks/{track_id}' #GET



HEADERS = {
	"Host": "us.api.iheart.com",
	"User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:68.0) Gecko/20100101 Firefox/68.0",
	"Accept": "application/json, text/plain, */*",
	"Accept-Language": "en-US,en;q=0.5",
	"Accept-Encoding": "gzip, deflate, br",
	"Referer": "https://www.iheart.com/",
	"X-hostName": "webapp.US",
	"X-Locale": "en-US",
	"Origin": "https://www.iheart.com",
	"DNT": "1",
	"Connection": "keep-alive"
}

CWD = os.path.dirname(os.path.realpath(__file__))
UUID_STORE = os.path.join(CWD, "iheart.uuid")


class Colors(object):
	RED = 31
	GREEN = 32
	YELLOW = 93#33
	BLUE = 34
	PINK = 35
	LIGHT_BLUE = 36
	WHITE = 37
	GRAY = 90
	CYAN = 96

	@staticmethod
	def colorize(message, color, bold=False):
		if isinstance(color, list):
			color = random.choice(color)
		color_code = '{};{}'.format(1 if bold else 0, color)
		# return "\u001b[{}m".format(color_code)+message+"\u001b[0m"
		return "\033[{}m".format(color_code)+message+"\033[0m"


def generic_get(url):
	res = requests.get(url, headers=HEADERS)
	try:
		return res.json()
	except:
		raise Exception(res.text)

# **************************************************************************************
# ********************************** API Functions *************************************
# **************************************************************************************


def ilogin(uuid_store):
	global HEADERS
	accessToken = 'anon'
	uu = ''
	if os.path.isfile(uuid_store):
		with open(uuid_store, 'r') as u:
			uu = u.read()
	if not uu:
		uu = str(uuid.uuid1())
	body = {
		'acessToken': accessToken,
		'accessTokenType': accessToken,
		'deviceId': uu,
		'deviceName': 'python-CLI',
		'host': 'webapp.US',
		'oauthUuid': uu,
		'userName': accessToken+uu
	}
	res = requests.post(new_user_url, data=body, headers=HEADERS)
	if res.status_code == 200:
		with open(uuid_store, 'w') as u:
			u.write(uu)
		user = res.json()
		HEADERS.update({
			'X-Ihr-Profile-Id': str(user['profileId']),
			'X-Ihr-Session-Id': user['sessionId'],
			'X-User-Id': str(user['profileId']),
			'X-Session-Id': user['sessionId'],
		})
		return user
	else:
		raise Exception(res.text)


def iget_market_id(zipCode):
	return requests.get(markets_url.format(zipCode=zipCode), headers=HEADERS).json()['hits'][0]


def isearch(keyword, limit=30, marketId=159):
	res = requests.get(search_url, params={
		'boostMarketId': marketId,
		'maxRows':limit,
		'bundle':True,
		'keyword':True,
		'keywords': keyword,
	}, headers=HEADERS)
	return res.json()


def iget_station_streams(stream_id):
	if isinstance(stream_id, (list, set)):
		stream_id = ','.join(stream_id)
	res = requests.get(station_stream_url.format(stream_id=stream_id), headers=HEADERS).json()
	if 'hits' in res:
		return res['hits'][0].get("streams") or []
	else:
		raise Exception(str(res))

def iget_live_meta(stream_id):
	return generic_get(meta_url.format(stream_id=stream_id))



def iget_artist_profile(artist_id):
	return generic_get(artist_profile_url.format(artist_id=artist_id))

def iget_artist_bio(artist_id):
	return generic_get(artist_url.format(artist_id=artist_id))


def iget_artist_station(user_id, artist_id):
	res = requests.post(
		artist_playlist_url.format(user_id=user_id, artist_id=artist_id),
		data={'contentId':artist_id},
		headers=HEADERS
	)
	try:
		return res.json()
	except:
		raise Exception(res.text)


def iget_artist_streams(astream_id):
	res = requests.post(artist_stream_url, json={
		'hostName': 'webapp.US',
		'playedFrom': 1,
		'stationId': astream_id,
		'stationType': 'RADIO'
	}, headers=HEADERS)
	try:
		return res.json().get('items') or []
	except:
		raise Exception(res.text)


def iget_track_info(track_id):
	return generic_get(track_url.format(track_id=track_id))


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
		if self._manager is not None:
			self._manager.event_attach(event_type, callback)
		else:
			self._events_registry[event_type] = callback

	def play(self):
		self.stop()
		self.inst = vlc.Instance("--adaptive-use-access") # Create a VLC instance
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

	def forward(self):
		"""Go forward one sec"""
		player = self.get_internal_player()
		player.set_time(player.get_time() + 10000)

	def rewind(self):
		"""Go back one sec"""
		player = self.get_internal_player()
		player.set_time(player.get_time() - 10000)

	def toggle_pause(self, pause=True):
		self.plr.set_pause(1 if pause else 0)
		self._paused = pause
		time.sleep(0.1)
		return self.is_playing()
		# return self.plr.get_state()




class Station(object):

	def __init__(self, station_id, mrl=None):
		self.id = station_id
		self.mrl = mrl

	def __str__(self):
		return "<station:{}:{}>".format(self.id, self.mrl)

	def __repr__(self):
		return str(self)

	def play(self):
		if self.mrl is not None:
			VLCPlayer.get_player(self.mrl).play()

	def toggle_pause(self, pause=True):
		if self.mrl is not None:
			return VLCPlayer.get_player(self.mrl).toggle_pause(pause=pause)

	def stop(self):
		if self.mrl is not None:
			VLCPlayer.get_player(self.mrl).stop()

	def is_playing(self):
		return self.mrl is not None and VLCPlayer.get_player(self.mrl).is_playing()

	def is_paused(self):
		return self.mrl is not None and VLCPlayer.get_player(self.mrl).is_paused()

	def forward(self):
		if self.mrl is not None:
			VLCPlayer.get_player(self.mrl).forward()

	def rewind(self):
		if self.mrl is not None:
			VLCPlayer.get_player(self.mrl).forward()

	def info(self):
		return {'mrl': self.mrl, 'id': self.id}

	def show_time(self, show=True):
		pass




class RadioStation(Station):
	def __init__(self, station_dict, search_term):
		self._station_dict = station_dict
		if 'id' not in self._station_dict:
			raise Exception("station id not found")
		super().__init__(station_id=self._station_dict['id'])
		# self.id = station_dict['id']
		self.name = self._station_dict.get('name')
		self.description = (self._station_dict.get('description') or '').strip()
		self.callLetters = self._station_dict.get('callLetters')
		self.frequency = self._station_dict.get('frequency')
		self.imageUrl = self._station_dict.get('imageUrl')

		self.search_term = search_term
		self.search_score = self._station_dict.get('score')

	def __str__(self):
		decor = Colors.colorize("**", Colors.RED)
		return "{} LiveStation: {}:{} {}".format(
			decor,
			Colors.colorize(self.name, Colors.CYAN, bold=True),
			Colors.colorize(self.description, Colors.BLUE, bold=True),
			decor
		)

	def _parse_stream(self):
		self.streams = iget_station_streams(self.id)
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
			Colors.colorize(self.description, Colors.PINK, bold=True),
			Colors.colorize(str(self.frequency)+"MHz", Colors.GREEN, bold=True),
			Colors.colorize("- "+self.mrl, Colors.GRAY, bold=False)
		))
		player = VLCPlayer.get_player(self.mrl)
		# player.register_event(player.POSITION_CHANGED, lambda e: sys.stdout.write(str(e.u.new_time)+"\r"+))
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
			return iget_live_meta(self.id)
		except Exception as e:
			print(e)




class Track(object):
	def  __init__(self, track_dict):
		if 'streamUrl' not in track_dict:
			raise Exception("station id not found")
		self._track_dict = track_dict
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

		self.__show_time = True

	def __str__(self):
		s = '''Track: "{}" by "{}" on "{}"'''.format(
			Colors.colorize(self.name, Colors.YELLOW, bold=True),
			Colors.colorize(self.artist, Colors.PINK, bold=True),
			Colors.colorize(self.album, Colors.GREEN, bold=True)
		)
		if self.version:
			s += " [" + Colors.colorize(self.version, Colors.RED, bold=True) + "]"
		return s

	def to_dict(self):
		return self._track_dict

	def __repr__(self):
		return str(self)

	def show_time(self, show=True):
		self.__show_time = show

	def _print_remaining_duration(self, event):
		if self.__show_time:
			remaining = int((1-event.u.new_position) * self.length)
			m = remaining // 60
			s = (remaining % 60)
			countdown = f"\t-{m:02d}:{s:02d}/{self.minutes:02d}:{self.seconds:02d}\r"
			sys.stdout.write(Colors.colorize(countdown, Colors.WHITE, bold=True))

	def play(self, on_complete):
		sys.stdout.write(Colors.colorize(self.mrl, Colors.GRAY) + "\n\r")
		sys.stdout.write(str(self) + "\n\r")
		player = VLCPlayer.get_player(self.mrl)
		player.register_event(player.END_REACHED, on_complete)
		player.register_event(player.POSITION_CHANGED, self._print_remaining_duration)
		player.play()




class ArtistStation(Station):
	def __init__(self, artist_dict, search_term, user_id):
		self.user_id = user_id
		self._artist_dict = artist_dict
		if 'id' not in self._artist_dict:
			raise Exception("station id not found")
		super().__init__(station_id=self._artist_dict['id'])

		self.name = self._artist_dict.get('name')
		self.imageUrl = self._artist_dict.get('image')

		self.search_term = search_term
		self.search_score = self._artist_dict.get('score')
		self.rank = self._artist_dict.get('rank')

		self.station_hash = None
		self.current_track = None

	def __str__(self):
		decor = Colors.colorize("**", Colors.RED)
		return "{} ArtistStation: {}:{} {}".format(
			decor,
			Colors.colorize(self.name, Colors.CYAN, bold=True),
			Colors.colorize(str(self.id), Colors.BLUE, bold=True),
			decor
		)

	def _track_gen(self):
		while True:
			station_data = iget_artist_station(self.user_id, self.id)
			self.station_hash = station_data['id']
			for trk_dict in iget_artist_streams(self.station_hash):
				yield Track(trk_dict)

	def get_current_track(self):
		return self.current_track

	def show_time(self, show=True):
		self.current_track.show_time(show)

	def _play_next(self, event, track_generator):
		self.current_track = next(track_generator)
		self.mrl = self.current_track.mrl
		_next_player = lambda next_event: self._play_next(event=next_event, track_generator=track_generator)
		self.current_track.play(on_complete=_next_player)

	def play(self):
		self._play_next(event=None, track_generator=self._track_gen())

	def info(self):
		try:
			return vars(self.current_track)
		except Exception as e:
			print(e)

	def forward(self):
		vlc_player = VLCPlayer.get_player(self.mrl).get_internal_player()
		vlc_player.set_time(vlc_player.get_length())




class Playlist(ArtistStation):

	def __init__(self, track_list, name):
		super().__init__({'id':name, 'name':name}, search_term=None, user_id=None)
		self.track_list = track_list

	def __str__(self):
		return "<Playlist :{}>".format(self.id)

	def _track_gen(self):
		while True:
			for trk_dict in self.track_list:
				yield Track(trk_dict)




class iHeart(object):

	TRACKS = 'tracks'
	ARTISTS = 'artists'
	ALBUMS = 'albums'
	STATIONS = 'stations'

	PLAYLISTS = 'playlists'
	PODCASTS = "podcasts"
	FEATURED_STATIONS = "featuredStations"
	TALKSHOWS = "talkShows"
	TALKTHEMES = "talkThemes"

	def __init__(self, uuid_store=UUID_STORE):
		self.user = ilogin(uuid_store=uuid_store)
		self.user_id = self.user['profileId']

	def search(self, keyword, category=None):
		if category is None: category = self.ARTISTS
		search_res = isearch(keyword)
		if category==self.STATIONS:
			return [RadioStation(res, search_term=keyword) for res in search_res['results'][category]]
		elif category==self.ARTISTS:
			return [ArtistStation(res, search_term=keyword, user_id=self.user_id) for res in search_res['results'][category]]
		else:
			return search_res['results'][category]



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
	artist.play()
	import json
	time.sleep(10)
	artist.stop()
	print(json.dumps({'a': artist.get_current_track().to_dict()}))



if __name__ == "__main__":
	test_artist_radio()
