import os, sys
import requests
import uuid
import vlc
import json
import time
import logging
import traceback
import threading

# Install VLC on windows
# certutil.exe -urlcache -split -f "https://get.videolan.org/vlc/3.0.8/win32/vlc-3.0.8-win32.exe" "vlc-3.0.8-win32.exe"
# vlc-3.0.8-win32.exe /L=1033 /S


new_user_url = 'https://us.api.iheart.com/api/v1/account/loginOrCreateOauthUser'
markets_url = 'https://us.api.iheart.com/api/v2/content/markets?countryCode=US&limit=1&cache=true&zipCode={zipCode}'
search_url = 'https://us.api.iheart.com/api/v3/search/all'

#stations
station_stream_url = 'https://us.api.iheart.com/api/v2/content/liveStations/{stream_id}'
meta_url = 'https://us.api.iheart.com/api/v3/live-meta/stream/{stream_id}/currentTrackMeta'



#TODO artist
artist_url = 'https://us.api.iheart.com/api/v1/catalog/getArtistByArtistId?artistId={artist_id}' #GET
artist_profile_url = 'https://us.api.iheart.com/api/v3/artists/profiles/{artist_id}' #GET
similar_artists_url = 'https://us.api.iheart.com/api/v1/catalog/artist/{artist_id}/getSimilar' #GET
artist_albums_url = 'https://us.api.iheart.com/api/v3/catalog/artist/{artist_id}/albums' #GET

artist_playlist_url = 'https://us.api.iheart.com/api/v2/playlists/{user_id}/ARTIST/{artist_id}' #POST formData = {'contentId':artist_id, 'playedFrom':10}
artist_stream_url = 'https://us.api.iheart.com/api/v2/playback/streams' # Takes steramId in POST params
# contentIds	[]
# hostName	webapp.US
# playedFrom	10
# stationId	5d82d62497758a0001bfffc3
# stationType	RADIO



#TODO tracks
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



printjson = lambda j: print(json.dumps(j, indent=4))

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

# **************************************************************************************
# ********************************** Player Classes ************************************
# **************************************************************************************


class MediaPlayer(object):
	'''https://www.olivieraubert.net/vlc/python-ctypes/doc/'''
	PLAYER = None

	def __init__(self, mrl):
		self.mrl = mrl
		self.inst = None
		self.plr = None
		self.list_player = False

	@classmethod
	def get_player(cls, mrl):
		if cls.PLAYER is None:
			cls.PLAYER = cls(mrl)
		elif mrl!=cls.PLAYER.mrl:
			cls.PLAYER.stop()
			cls.PLAYER = cls(mrl)
		return cls.PLAYER

	def get_vlc_player(self):
		if self.list_player:
			return self.plr.get_media_player()
		else:
			return self.plr

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
		self.plr.play()


	def is_playing(self):
		return self.plr is not None and self.plr.is_playing()

	def stop(self):
		if self.plr is not None:
			self.plr.stop()
			self.plr.release()
			self.plr = None
		if self.inst is not None:
			self.inst.release()
			self.inst = None


	def forward(self):
		"""Go forward one sec"""
		player = self.get_vlc_player()
		player.set_time(player.get_time() + 10000)

	def rewind(self):
		"""Go back one sec"""
		player = self.get_vlc_player()
		player.set_time(player.get_time() - 10000)


	def toggle_pause(self, pause=True):
		self.plr.set_pause(1 if pause else 0)
		time.sleep(0.1)
		return self.is_playing()
		# return self.plr.get_state()







class RadioStation(object):
	def __init__(self, station_dict, search_term):
		if 'id' not in station_dict:
			raise Exception("station id not found")
		self.id = station_dict['id']
		self.name = station_dict.get('name')
		self.description = (station_dict.get('description') or '').strip()
		self.callLetters = station_dict.get('callLetters')
		self.frequency = station_dict.get('frequency')
		self.imageUrl = station_dict.get('imageUrl')
		self.mrl = None

		self.search_term = search_term
		self.search_score = station_dict.get('score')

	def __str__(self):
		return "<station:{}:{}>".format(self.name, self.description)

	def parse_stream(self):
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
		self.parse_stream()
		if self.mrl is None:
			raise Exception("Stream not available for {}".format(self))
		print("\nPlaying {} - {} at {} : {}".format(self.name, self.description, self.frequency, self.mrl))
		MediaPlayer.get_player(self.mrl).play()


	def toggle_pause(self, pause=True):
		if pause and self.is_playing():
			self.stop()
		elif not self.is_playing():
			self.play()

	def stop(self):
		if self.mrl is not None:
			MediaPlayer.get_player(self.mrl).stop()

	def is_playing(self):
		return self.mrl is not None and MediaPlayer.get_player(self.mrl).is_playing()

	def info(self):
		try:
			return iget_live_meta(self.id)
		except Exception as e:
			print(e)

	def forward(self):
		MediaPlayer.get_player(self.mrl).forward()

	def rewind(self):
		MediaPlayer.get_player(self.mrl).forward()




class Track(object):
	def  __init__(self, track_dict):
		# printjson(track_dict)
		if 'streamUrl' not in track_dict:
			raise Exception("station id not found")
		self.mrl = track_dict['streamUrl'].replace("https", 'http')

		content = track_dict['content']
		self.id = content['id']
		self.name = content.get('title')
		self.version = content.get('version')
		self.length = content.get('duration')
		self.artist = content.get('artistName')
		self.artist_id = content.get('artistId')
		self.album = content.get('albumName')
		self.album_id = content.get('albumId')
		self.lyrics_id = content.get('lyricsId')
		self.imageUrl = content.get('imagePath')

	def __str__(self):
		s = '''<Track: "{}" by "{}" on "{}"'''.format(self.name, self.artist, self.artist)
		if self.version is not None:
			s += " [" + self.version + "]"
		s += ">"
		return s

	def __repr__(self):
		return str(self)




class ArtistStation(object):
	def __init__(self, artist_dict, search_term, user_id):
		self.user_id = user_id

		self._artist_dict = artist_dict
		if 'id' not in self._artist_dict:
			raise Exception("station id not found")
		self.id = self._artist_dict['id']
		self.name = self._artist_dict.get('name')
		self.imageUrl = self._artist_dict.get('image')

		self.search_term = search_term
		self.search_score = self._artist_dict.get('score')
		self.rank = self._artist_dict.get('rank')

		self.station_id = None
		self.tracks = []
		self.current_track = None
		self.player_thread = None

	def __str__(self):
		return "<artist:{}:>".format(self.name)

	def _track_gen(self):
		while True:
			station_data = iget_artist_station(self.user_id, self.id)
			self.station_id = station_data['id']
			for strm in iget_artist_streams(station_data['id']):
				yield Track(strm)

	def get_current_track(self):
		return self.current_track


	def play(self):

		def _play():
			for self.current_track in self._track_gen():
				print("\r"+str(self.current_track))
				player = MediaPlayer.get_player(self.current_track.mrl)
				try:
					player.play()
					time.sleep(0.5)
					m = self.current_track.length // 60
					s = self.current_track.length % 60
					sys.stdout.write("\033[?25l")
					while player.is_playing():
						s = (s-1)%60
						if s==0:
							m-=1
						sys.stdout.write("\r{:02d}:{:02d}".format(m, s))
						time.sleep(1)
				except:
					traceback.print_exc()
					print("HOOO--------")
				finally:
					sys.stdout.write("\033[?25h")
					player.stop()

		self.player_thread = threading.Thread(target=_play)
		self.player_thread.daemon = True
		self.player_thread.start()
		try:
			self.player_thread.join()
		finally:
			sys.stdout.write("\033[?25h")
			sys.stdout.write("\n")
			MediaPlayer.get_player(self.current_track.mrl).stop()


	def toggle_pause(self, pause=True):
		if self.current_track is not None:
			return MediaPlayer.get_player(self.current_track.mrl).toggle_pause(pause=pause)

	def stop(self):
		if self.current_track is not None:
			MediaPlayer.get_player(self.current_track.mrl).stop()

	def is_playing(self):
		return self.current_track is not None \
			and self.player_thread is not None \
			and self.player_thread.is_alive() \
			and MediaPlayer.get_player(self.current_track.mrl).is_playing()

	def info(self):
		try:
			return vars(self.current_track)
		except Exception as e:
			print(e)

	def forward(self):
		MediaPlayer.get_player(self.current_track.mrl).forward()

	def rewind(self):
		MediaPlayer.get_player(self.current_track.mrl).forward()





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



def test_stations():
	radio = iHeart()
	res = radio.search("Classic Rock", category=iHeart.STATIONS)
	# res[2].play()
	# time.sleep(5)
	# print(res[2].is_playing())
	# time.sleep(5)
	# res[2].stop()
	for station in res[:4]:
		station.play()
		time.sleep(10)
		station.stop()
		time.sleep(2)



def test_artist_radio():
	if len(sys.argv) > 1:
		artist_keyword = sys.argv[1].strip()
	else:
		artist_keyword = input("Search for artist: ")
	radio = iHeart()
	artists = radio.search(artist_keyword, category=iHeart.ARTISTS)
	artists[0].play()



if __name__ == "__main__":
	test_artist_radio()