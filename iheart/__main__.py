import os, sys
import traceback
from collections import OrderedDict
import json

from iheart import (
	iHeart,
	Track,
	Station,
	LiveStation,
	SongStation,
	ArtistStation,
)
from iheart.colors import Colors


try:
	from msvcrt import getch
except ImportError:
	import termios
	import tty
	def getch():  # getchar(), getc(stdin)  #PYCHOK flake
		fd = sys.stdin.fileno()
		old = termios.tcgetattr(fd)
		try:
			tty.setraw(fd)
			ch = sys.stdin.read(1)
		finally:
			termios.tcsetattr(fd, termios.TCSADRAIN, old)
			return ch


printjson = lambda j: print(json.dumps(j, indent=4))
wipeline = lambda:sys.stdout.write("\33[2K\r")



class Playlist(ArtistStation):
	'''Json stored playlist implementation using ArtistRadio'''
	def __init__(self, playlist_dict):
		self.__dict = playlist_dict
		self.name = playlist_dict['name']
		super().__init__({'id': self.name, 'name': self.name, 'user_id':None})
		self.track_list = [Track(trk_dict) for trk_dict in playlist_dict['track_dict_list']]

	def get_dict(self):
		return self.__dict

	def __str__(self):
		return "<Playlist: {}>".format(Colors.colorize(self.id, Colors.CYAN))

	def iter_tracks(self):
		while True:
			for trk in self.track_list:
				yield trk


class iHeart_Storage(object):

	DATA = {
		'last_played': None,
		'playlists': {},
	}

	CONFIG = {}

	_STATION_CLASS_MAP = {
		ArtistStation.__name__: ArtistStation,
		LiveStation.__name__: LiveStation,
		SongStation.__name__: SongStation,
		Station.__name__: Station,
		Playlist.__name__: Playlist
	}

	def __init__(self, configdir, debug=False):
		self._debug = debug
		self.configdir = configdir
		self.CONFIG = self._load_config()
		self.DATA = self._load_data()

	def _load_config(self):
		if not os.path.isdir(self.configdir): os.makedirs(self.configdir)
		temp_conf = {
			'last-played-file': os.path.join(self.configdir, 'last_played.json'),
			'playlist-dir-path': os.path.join(self.configdir, 'playlists'),
		}
		conf_file = os.path.join(self.configdir, 'config.json')
		try:
			with open(conf_file, 'r') as conf:
				for k,v in json.load(conf).items():
					temp_conf[k] = v
		except Exception as e:
			if self._debug: print(e)
		if not os.path.isdir(temp_conf['playlist-dir-path']):
			os.makedirs(temp_conf['playlist-dir-path'])

		with open(conf_file, 'w') as conf:
			json.dump(temp_conf, conf, indent=4)
		return temp_conf

	def _load_data(self):
		default_data = self.DATA.copy()
		if os.path.isfile(self.CONFIG['last-played-file']):
			try:
				with open(self.CONFIG['last-played-file'], 'r') as conf:
					default_data['last_played'] = json.load(conf, object_pairs_hook=OrderedDict)
			except Exception as e:
				if self._debug: print(e)
		for f in os.listdir(self.CONFIG['playlist-dir-path']):
			if f.endswith('.playlist.json'):
				pl_name = f.replace(".playlist.json", "")
				try:
					with open(os.path.join(self.CONFIG['playlist-dir-path'], f), 'r') as pl:
						default_data['playlists'][pl_name] = json.load(pl, object_pairs_hook=OrderedDict)
				except Exception as e:
					if self._debug: print(e)
		return default_data

	def write(self):
		for pl_name, obj in self.get_playlists().items():
			pl_file = os.path.join(self.CONFIG['playlist-dir-path'], '{}.playlist.json'.format(pl_name))
			with open(pl_file, 'w') as pl:
				json.dump(obj, pl, indent=4)

		with open(self.CONFIG['last-played-file'], 'w') as conf:
			conf.write(json.dumps(self.DATA['last_played'], indent=4))

	def station_to_dict(self, station_instance):
		d = station_instance.get_dict()
		d['__name__'] = station_instance.__class__.__name__
		d['__id__'] = station_instance.id
		return d

	def station_from_dict(self, d):
		if '__name__' not in d:
			raise Exception("Not a Track/Station dict")
		return self._STATION_CLASS_MAP[d['__name__']](d)

	def current_track_to_dict(self, station_instance):
		if isinstance(station_instance, (ArtistStation, SongStation)):
			track = station_instance.get_current_track()
			if track:
				return self.station_to_dict(track)
			else:
				return {}
		else:
			return self.station_to_dict(station_instance)

	def update_last_played(self, track):
		if not isinstance(track, dict):
			 track = self.station_to_dict(track)
		self.DATA['last_played'] = track

	def add_to_playlist(self, playlist_name, track):
		if not isinstance(track, dict):
			track = self.current_track_to_dict(track)
		if playlist_name not in self.DATA['playlists']:
			self.DATA['playlists'][playlist_name] = OrderedDict()
		if track['__id__'] not in self.DATA['playlists'][playlist_name]:
			self.DATA['playlists'][playlist_name][track['__id__']] = track #__id__ is unique iheart id

	def get_playlists(self):
		return self.DATA['playlists']




class ExitException(Exception):
	pass


class iHeart_CLI(iHeart):

	CATEGORIES = OrderedDict({
		iHeart.ARTISTS: 'Artist Radio',
		iHeart.TRACKS: 'Song Radio',
		iHeart.STATIONS: "Live Radio",
		iHeart.PLAYLISTS: 'Playlists',
	})

	ALL_CONTROLS = OrderedDict({
		'?': 'help',
		'p': 'pause-play',
		'n': 'next',
		'i': 'information',
		'+': 'add-to-playlist',
		'l': 'list-last-search',
		's': 'search-stations',
		'c': 'change-category',
		'q': 'exit',
		' ': 'pause-play', # implied (will not display in help)
		'\r': 'print-current', # implied (will not display in help)
	})

	CONTROLS = ALL_CONTROLS.copy()

	def __init__(self, configdir, category=None, debug=False):
		uuid_file = os.path.join(configdir, "iheart-api.uuid")
		super().__init__(uuid_store=uuid_file, print_url=False)
		self.store = iHeart_Storage(configdir=configdir, debug=debug)
		self._category = category or iHeart.ARTISTS
		self.station_list = []
		self.station = None
		self._debug = debug

	def print_help(self):
		wipeline()
		for cmd, action in self.CONTROLS.items():
			if cmd.strip() != '': # ignore the implied controls that cannot be printed
				print("\t", cmd, "  ", action)

	def choose_category(self, force=True):
		print("Pick a category -")
		pl = self.store.get_playlists()
		playlist_count = len(pl)
		cats = []
		cats_actual = list(self.CATEGORIES.keys())
		for c in self.CATEGORIES:
			if c==iHeart.PLAYLISTS and playlist_count==0:
				continue
			cats.append(self.CATEGORIES[c])

		for i, s in enumerate(cats):
			print("\t", Colors.colorize(str(i), Colors.YELLOW), ")", s)
		try:
			choice = input("Pick: ").strip()
			if not choice or not choice.isnumeric() or int(choice)>=len(cats):
				raise Exception("Invalid choice!")
			else:
				self._category = cats_actual[int(choice)]
				# Modifying controls based on choice
				self.CONTROLS = self.ALL_CONTROLS.copy()
				if self._category == iHeart.PLAYLISTS:
					del self.CONTROLS['s'] # No search when in playlists
					self.CONTROLS['l'] = 'list-playlist-tracks' # List tracks when in playlists
				elif self._category == iHeart.STATIONS:
					del self.CONTROLS['+'] # Cannot add live stations to playlists

		except Exception as e:
			if self._debug: print(e)
			if force: self.choose_category()

	def search_stations(self, keyword=None):
		try:
			if keyword is None:
				keyword = input("Search {}: ".format(self.CATEGORIES[self._category]))
			if not keyword.strip():
				raise Exception("No keyword found")
			self.station_list = self.search(keyword.strip(), category=self._category)
			return self.list_current_stations()
		except Exception as e:
			if self._debug: print(e)
			return None

	def list_current_stations(self):
		try:
			if len(self.station_list)==0:
				raise Exception("No stations found")
			for i, s in enumerate(self.station_list):
				print("\t", Colors.colorize(str(i), Colors.YELLOW), ")", s.name)

			choice = input("Choice: ").strip()
			if not choice or not choice.isnumeric() or int(choice)>=len(self.station_list):
				raise Exception("Invalid choice!")
			else:
				return self.station_list[int(choice)]
		except Exception as e:
			if self._debug: print(e)
			return None


	def add_to_playlist(self):
		try:
			print("Add track to playlist -")
			pl = self.store.get_playlists()
			pl_names = list(pl.keys()) + ['( New Playlist )']
			for i, s in enumerate(pl_names):
				plen_disp = ''
				if s in pl:
					plen = len(pl[s])
					plen_comment = "tracks" if plen>1 else "track"
					plen_disp = "[{} {}]".format(plen, plen_comment)
				print("\t", Colors.colorize(str(i), Colors.YELLOW), ")", s, plen_disp)

			choice = input("Choice: ").strip()
			if not choice or not choice.isnumeric() or int(choice)>=len(pl_names):
				raise Exception("Invalid choice!")
			elif int(choice)==len(pl_names)-1:
				new_pl = input("Name the new playlist: ").strip()
				if new_pl:
					self.store.add_to_playlist(playlist_name=new_pl, track=self.station)
				else:
					if self._debug: print("No playlist name provided!")
			else:
				self.store.add_to_playlist(playlist_name=pl_names[int(choice)], track=self.station)
			self.store.write()

		except Exception as e:
			if self._debug: print(e)
			traceback.print_exc()

	def choose_playlist(self):
		try:
			print("Choose playlist -")
			pl = self.store.get_playlists()
			pl_names = list(pl.keys())
			for i, s in enumerate(pl_names):
				plen_disp = ''
				if s in pl:
					plen = len(pl[s])
					plen_comment = "tracks" if plen>1 else "track"
					plen_disp = "[{} {}]".format(plen, plen_comment)
				print("\t", Colors.colorize(str(i), Colors.YELLOW), ")", s, plen_disp)

			choice = input("Choice: ").strip()
			if not choice or not choice.isnumeric() or int(choice)>=len(pl_names):
				raise Exception("Invalid choice!")
			else:
				pl_choice = pl_names[int(choice)]
				track_dict_list = list(pl[pl_choice].values())
				pl_dict = {'name': pl_choice, 'track_dict_list': track_dict_list}
				return Playlist(pl_dict)
		except Exception as e:
			if self._debug: print(e)
			return None

	def get_command(self):
		cmd = getch().lower()
		if isinstance(cmd, bytes): cmd = cmd.decode('utf-8', errors='ignore')
		return (self.CONTROLS.get(cmd) or '').lower()


	def run_cli(self, search_term=None):
		cmd = ''
		new_station = None

		try:
			while True:
				if new_station is not None:
					self.station = new_station
					self.station.stop()
					new_station = None
					continue

				elif self.station is None:
					if self._category == iHeart.PLAYLISTS:
						# highjacking playlist category for Json stored implementation
						self.station = self.choose_playlist()
					else:
						self.station = self.search_stations(keyword=search_term)
					new_station = None
					continue

				elif not self.station.is_playing() and not self.station.is_paused(): # station is not None
					print(self.station)
					self.station.play()
					self.store.update_last_played(self.station)
					self.store.write()

				while True:
					self.station.show_time(True)
					cmd = self.get_command()
					wipeline()
					if cmd == 'exit':
						raise ExitException("Exit!")

					elif cmd == 'print-current':
						self.station.show_time(False)
						if self._category == iHeart.STATIONS:
							print(self.station)
						else:
							print(self.station.current_track)

					elif cmd == 'change-category':
						# old_cat = self._category
						self.station.show_time(False)
						self.choose_category(force=False)
						# if self._category!=old_cat:
						if self._category == iHeart.PLAYLISTS:
							# highjacking playlist category for Json stored implementation
							new_station = self.choose_playlist()
						else:
							new_station = self.search_stations()
						break

					elif cmd == 'pause-play':
						if self.station.is_playing():
							self.station.toggle_pause(True)
							sys.stdout.write("paused\r")
						else:
							self.station.toggle_pause(False)

					elif cmd == 'list-playlist-tracks': # Only for playlist mode
						print(self.station)
						print("[", end="")
						print(*["\n\t{}. {}".format(i+1,t) for i,t in enumerate(self.station.track_list)])
						print("]")

					elif cmd == 'list-last-search': # No search when in playlists
						self.station.show_time(False)
						new_station = self.list_current_stations()
						break

					elif cmd == 'search-stations': # No search when in playlists
						self.station.show_time(False)
						new_station = self.search_stations()
						break

					elif cmd == 'information':
						printjson(self.station.info())

					elif cmd == 'next':
						self.station.forward()

					elif cmd == 'help':
						self.print_help()

					elif cmd == 'add-to-playlist':
						self.station.show_time(False)
						self.add_to_playlist()

		except:
			self._debug: traceback.print_exc()
			raise
		finally:
			if self.station is not None:
				self.station.stop()
				self.station = None




def main():
	if '-d' in sys.argv or '--debug' in sys.argv:
		debug = True
		if '--debug' in sys.argv: sys.argv.remove('--debug')
		if '-d' in sys.argv: sys.argv.remove('-d')
	else:
		debug = False

	if len(sys.argv) > 1:
		search_term = sys.argv[1].strip()
	else:
		search_term = None


	configdir = os.path.join(
		os.environ.get('APPDATA') or
		os.environ.get('XDG_CONFIG_HOME') or
		os.path.join(os.environ['HOME'], '.config'),
		"iheartcli"
	)
	if not os.path.isdir(configdir): os.makedirs(configdir)

	try:
		radio = iHeart_CLI(configdir, debug=debug)
		radio.choose_category()
		radio.run_cli(search_term)
	except KeyboardInterrupt:
		print("KeyboardInterrupt")
	except Exception as e:
		if debug: traceback.print_exc()
		print(e)



if __name__ == "__main__":
	main()
