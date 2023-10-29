import os
import json
from collections import OrderedDict
from datetime import datetime as dt

from .stations import (
	iHeartSongStation,
	iHeartArtistStation,
)
from .conf import ConfigurationManager



class iRadio_Storage(object):

	DATA = {
		'last_played': None,
		'playlists': {},
	}

	def __init__(self, config_manager: ConfigurationManager, supported_stations: list=[]):
		self._config_manager = config_manager
		self._debug = os.environ.get('RADIO_DEBUG') == "1"
		self._config = self._load_config()
		self._data = self._load_data()
		self._STATION_CLASS_MAP = {s.__name__: s for s in supported_stations}
		# history
		self._current_track = None
		self._current_track_start_dt = None
		self._session_name = dt.now().strftime("SESSION-%Y-%m-%d--%H-%M-%S")
		self._session_hist = []


	def _load_config(self):
		datadir = self._config_manager.get_datadir()
		if not os.path.isdir(datadir):
			os.makedirs(datadir)
		temp_conf = {
			'last-played-file': os.path.join(datadir, 'last_played.json'),
			'playlist-dir-path': os.path.join(datadir, 'playlists'),
			'history-dir-path': os.path.join(datadir, 'history'),
			'track-history': self._config_manager.get_bool(key='track-history', default=True),
			'history-min-play-seconds': self._config_manager.get_int(key='history-min-play-seconds', default=10), # only songs that are atleast played for this long get saved in history
		}
		if not os.path.isdir(temp_conf['playlist-dir-path']):
			os.makedirs(temp_conf['playlist-dir-path'])
		if not os.path.isdir(temp_conf['history-dir-path']):
			os.makedirs(temp_conf['history-dir-path'])
		return temp_conf


	def _load_data(self):
		default_data = self.DATA.copy()
		if os.path.isfile(self._config['last-played-file']):
			try:
				with open(self._config['last-played-file'], 'r') as conf:
					default_data['last_played'] = json.load(conf, object_pairs_hook=OrderedDict)
			except Exception as e:
				if self._debug: print(e)
		for f in os.listdir(self._config['playlist-dir-path']):
			if f.endswith('.playlist.json'):
				pl_name = f.replace(".playlist.json", "")
				try:
					with open(os.path.join(self._config['playlist-dir-path'], f), 'r') as pl:
						default_data['playlists'][pl_name] = json.load(pl, object_pairs_hook=OrderedDict)
				except Exception as e:
					if self._debug: print(e)
		return default_data


	def write(self):
		for pl_name, obj in self.get_playlists().items():
			pl_file = os.path.join(self._config['playlist-dir-path'], '{}.playlist.json'.format(pl_name))
			with open(pl_file, 'w') as pl:
				json.dump(obj, pl, indent=4, default=str)

		with open(self._config['last-played-file'], 'w') as conf:
			conf.write(json.dumps(self._data['last_played'], indent=4, default=str))


	# converters
	def station_to_dict(self, station_instance):
		d = station_instance.get_dict()
		d['__name__'] = station_instance.__class__.__name__
		d['__id__'] = station_instance.id
		return d


	def station_from_dict(self, d):
		if '__name__' not in d:
			raise Exception("Not a Track/Station dict")
		if d['__name__'] not in self._STATION_CLASS_MAP:
			raise Exception("Unsupported Track/Station - {}".format(d['__name__']))
		return self._STATION_CLASS_MAP[d['__name__']](d)


	def current_track_to_dict(self, station_instance):
		if isinstance(station_instance, (iHeartArtistStation, iHeartSongStation)):
			track = station_instance.get_current_track()
			if track:
				return self.station_to_dict(track)
			else:
				return {}
		else:
			return self.station_to_dict(station_instance)

	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
	# -=-=-=-=-=-=-=-= Playlist ops -=-=-=-=-=-=-=-=-=
	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

	def add_to_playlist(self, playlist_name, track):
		if not isinstance(track, dict):
			track = self.current_track_to_dict(track)
		if playlist_name not in self._data['playlists']:
			self._data['playlists'][playlist_name] = OrderedDict()
		if '__id__' in track:
			track_id = str(track['__id__']) # json.dump automatically converts keys to strings. make it explicit!
			if track_id not in self._data['playlists'][playlist_name]:
				self._data['playlists'][playlist_name][track_id] = track #__id__ is unique iheart id
			self.write()


	def delete_from_playlist_by_id(self, playlist_name, track_id):
		track_id = str(track_id) # json.dump automatically converts keys to strings. make it explicit!
		if playlist_name in self._data['playlists'] and track_id in self._data['playlists'][playlist_name]:
			del self._data['playlists'][playlist_name][track_id]
			self.write()


	def get_playlists(self):
		return self._data['playlists']

	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
	# -=-=-=-=-=-=-=-= History ops -=-=-=-=-=-=-=-=-=-
	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

	def update_last_played(self, track): # this is called when station changes
		if not isinstance(track, dict):
			track = self.station_to_dict(track)
		self._data['last_played'] = track
		self.write()


	def now_playing(self, track):
		if self._config['track-history']:
			if self._current_track is not None and self._current_track_start_dt is not None:
				end_dt = dt.now()
				duration = (end_dt - self._current_track_start_dt).total_seconds()
				if duration >= self._config.get('history-min-play-seconds', 0): # if the song was atleast played for these many seconds, we will store it in history
					track_dict = self.current_track_to_dict(self._current_track)
					track_dict['play_start_dt'] = self._current_track_start_dt
					track_dict['play_end_dt'] = end_dt
					track_dict['played_duration'] = duration
					self._session_hist.append(track_dict)

					with open(os.path.join(self._config['history-dir-path'], self._session_name), 'w') as sess:
						sess.write(json.dumps(self._session_hist, indent=4, default=str))

			self._current_track = track
			self._current_track_start_dt = dt.now()
