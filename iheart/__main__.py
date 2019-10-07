import os, sys
import traceback
from collections import OrderedDict
import json

from iheart import * #pylint: disable=unused-wildcard-import


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
		return "<Playlist: {}>".format(self.id)

	def _track_gen(self):
		while True:
			for trk in self.track_list:
				yield trk


class iHeart_Storage(object):

	DATA = {
		'last_played': None,
		'playlists': {},
	}

	_STATION_CLASS_MAP = {
		ArtistStation.__name__: ArtistStation,
		LiveStation.__name__: LiveStation,
		SongStation.__name__: SongStation,
		Station.__name__: Station,
		Playlist.__name__: Playlist
	}

	def __init__(self, configdir):
		self.configdir = configdir
		self.data_file = os.path.join(self.configdir, 'iheart-data.json')
		self.DATA = self._load_data()

	def _load_data(self):
		default_data = self.DATA.copy()
		if os.path.isfile(self.data_file):
			try:
				with open(self.data_file, 'r') as conf:
					return json.load(conf, object_pairs_hook=OrderedDict)
			except:
				pass
		return default_data

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
		self.DATA['playlists'][playlist_name][track['__id__']] = track

	def get_playlists(self):
		return self.DATA['playlists']

	def write(self):
		with open(self.data_file, 'w') as conf:
			conf.write(json.dumps(self.DATA, indent=4))


class ExitException(Exception):
	pass


class iHeart_CLI(iHeart):

	CATEGORIES = OrderedDict({
		'Artist Radio': iHeart.ARTISTS,
		'Song Radio': iHeart.TRACKS,
		"Live Radio": iHeart.STATIONS,
		'Playlists': iHeart.PLAYLISTS,
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
	})

	CONTROLS = ALL_CONTROLS.copy()

	def __init__(self, configdir, category=None, debug=False):
		uuid_file = os.path.join(configdir, "iheart-cli.uuid")
		super().__init__(uuid_store=uuid_file)
		self.store = iHeart_Storage(configdir=configdir)
		self._category = category or iHeart.ARTISTS
		self.station_list = []
		self.station = None
		self._debug = debug

	def print_help(self):
		wipeline()
		for cmd, action in self.CONTROLS.items():
			print("\t", cmd, "  ", action)

	def choose_category(self, force=True):
		print("Pick a category -")
		pl = self.store.get_playlists()
		playlist_count = len(pl)
		cats = []
		for c in self.CATEGORIES:
			if self.CATEGORIES[c]==iHeart.PLAYLISTS and playlist_count==0:
				continue
			cats.append(c)

		for i, s in enumerate(cats):
			print("\t", i, ")", s)
		try:
			choice = input("Pick: ").strip()
			if not choice or not choice.isnumeric() or int(choice)>=len(cats):
				raise Exception("Invalid choice!")
			else:
				self._category = self.CATEGORIES[cats[int(choice)]]
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
				keyword = input("Search for station: ")
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
				print("\t", i, ")", s.name)

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
			pl_names = ['* New PLaylist']+list(pl.keys())
			for i, s in enumerate(pl_names):
				pl_len_disp = "[{}]".format(len(pl[s])) if s in pl else ''
				print("\t", i, ")", s, pl_len_disp)

			choice = input("Choice: ").strip()
			if not choice or not choice.isnumeric() or int(choice)>=len(pl_names):
				raise Exception("Invalid choice!")
			elif int(choice)==0:
				new_pl = input("Name the new playlist: ").strip()
				self.store.add_to_playlist(playlist_name=new_pl, track=self.station)
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
				pl_len_disp = "[{}]".format(len(pl[s])) if s in pl else ''
				print("\t", i, ")", s, pl_len_disp)

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
		cmd = getch().strip().lower()
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
					elif cmd == 'change-category':
						old_cat = self._category
						self.station.show_time(False)
						self.choose_category(force=False)
						if self._category!=old_cat:
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
						print(self.station, "[", end="")
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
