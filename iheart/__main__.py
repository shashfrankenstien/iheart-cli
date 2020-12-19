import os, sys
import traceback
from collections import OrderedDict, deque
import json
import random
import argparse

from iheart import (
	__version__,
	vlc_is_installed,
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
app_msg_color = lambda m: Colors.colorize(m, Colors.YELLOW, bold=False)


WELCOME_MSG = '''Welcome to iHeart cli player ({})!
Type '?' during playback to show available commands.'''.format(__version__)

WELCOME_MSG = app_msg_color(WELCOME_MSG)


class Playlist(ArtistStation):
	'''Json stored playlist implementation using ArtistRadio'''
	def __init__(self, playlist_dict):
		self.__dict = playlist_dict
		self.name = playlist_dict['name']
		super().__init__({'id': self.name, 'name': self.name, 'user_id':None})
		self.track_list = deque([Track(trk_dict) for trk_dict in playlist_dict['track_dict_list']]) # deque so as to use rotate
		self.tracks_to_play = self.track_list.copy() # make copy to implement shuffle
		self.shuffle = False
		self.now_playing_id = None

	def get_dict(self):
		return self.__dict

	def __str__(self):
		return "<Playlist: {}> {}".format(
			Colors.colorize(self.id, Colors.CYAN),
			Colors.colorize("[Shuffle]", Colors.PINK) if self.shuffle else '',
		)

	def iter_tracks(self):
		while True:
			new_track = self.tracks_to_play[0]
			self.now_playing_id = new_track.id
			yield new_track
			self.tracks_to_play.rotate(-1) # rotate left to go to next track

	def toggle_shuffle(self):
		self.shuffle = not self.shuffle
		if self.shuffle:
			random.shuffle(self.tracks_to_play) # shuffle playlist
		else: # shuffle off
			# if there is a song playing in shuffle mode,
			# rotate tracklist such that the playlist continues from the current track
			current_idx = 0
			if self.now_playing_id is not None:
				for i, t in enumerate(self.track_list):
					if t.id==self.now_playing_id:
						current_idx = i
						break

			self.tracks_to_play = self.track_list.copy() # make copy of original track list
			self.tracks_to_play.rotate(-1*current_idx) # rotate left to current track

	def jump_to(self, idx):
		if idx < len(self.track_list):
			track = self.track_list[idx]
			for i, t in enumerate(self.tracks_to_play):
				if t.id==track.id:
					self.tracks_to_play.rotate(-1*(i-1)) # rotate left so that selected track will play next
					self.forward() # then trigger jump to next song
					break


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

	COMMON_CONTROLS = OrderedDict({
		'?': 'help',
		'p': 'pause-play',
		'n': 'next',
		'r': 'repeat-track-toggle',
		'i': 'information',
		'+': 'add-to-playlist',
		'l': 'list-last-search',
		's': 'search-station',
		'c': 'change-category',
		'q': 'exit',
		' ': 'pause-play', # <SPACEBAR> implied (will not display in help)
		'\r': 'print-current', # <RETURN> (will not display in help)
	})

	CONTROLS = COMMON_CONTROLS.copy() # this copy might be modified downstream according to type of station

	def __init__(self, configdir, debug=False):
		uuid_file = os.path.join(configdir, "iheart-api.uuid")
		super().__init__(uuid_store=uuid_file, print_url=False)
		self.store = iHeart_Storage(configdir=configdir, debug=debug)
		self.station_list = []
		self._station = None
		self._debug = debug


	def print_help(self):
		wipeline()
		for cmd, action in self.CONTROLS.items():
			if cmd.strip() != '': # ignore the implied controls that cannot be printed
				print("\t", app_msg_color(cmd), "  ", action)

	@property
	def category(self):
		# category getter to convert current station to it's category
		if isinstance(self.station, LiveStation):
			return iHeart.STATIONS
		# ArtistStation should be checked for after checking for it's subclasses - SongStation and Playlist
		elif isinstance(self.station, SongStation):
			return iHeart.TRACKS
		elif isinstance(self.station, Playlist):
			return iHeart.PLAYLISTS
		elif isinstance(self.station, ArtistStation):
			return iHeart.ARTISTS
		else:
			return None


	@property
	def station(self):
		return self._station

	@station.setter
	def station(self, station):
		# Modifying controls based on selected station type
		self.CONTROLS = self.COMMON_CONTROLS.copy()
		if isinstance(station, Playlist):
			self.CONTROLS['s'] = 'shuffle-playlist-toggle' # No search when in playlists, instead, use 's' for shuffle
			self.CONTROLS['l'] = 'list-playlist-tracks' # List tracks when in playlists
			self.CONTROLS['j'] = 'jump-to-track' # Jump to track by index in playlist
		elif isinstance(station, LiveStation):
			del self.CONTROLS['+'] # Cannot add live stations to playlists

		self.CONTROLS.move_to_end('q') # make exit / quit the last option
		self._station = station


	def station_picker(self, category=None, keyword=None, force=True):
		# wrapper to pick category and accordingly select station
		if category is None:
			category = self.choose_category(force=force)

		if category == iHeart.PLAYLISTS:
			# highjacking playlist category for Json stored implementation
			return self.choose_playlist()
		else:
			return self.search_stations(category=category, keyword=keyword)


	def choose_category(self, force=True):
		print("Pick a category -")
		pl = self.store.get_playlists()
		playlist_count = len(pl)
		cats = []
		cats_consts = []
		for c in self.CATEGORIES:
			if c==iHeart.PLAYLISTS and playlist_count==0:
				continue
			cats_consts.append(c)
			cats.append(self.CATEGORIES[c])

		for i, s in enumerate(cats):
			print("\t", app_msg_color(str(i)), ")", s)
		try:
			choice = input("Pick: ").strip()
			if not choice or not choice.isnumeric() or int(choice)>=len(cats):
				raise Exception("Invalid choice!")
			else:
				return cats_consts[int(choice)]
		except Exception as e:
			if self._debug: print(e)
			if force:
				return self.choose_category(force=force)


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
				print("\t", app_msg_color(str(i)), ")", s, plen_disp)

			choice = input("Choice: ").strip()
			if not choice or not choice.isnumeric() or int(choice)>=len(pl_names):
				raise Exception("Invalid choice!")
			else:
				return self.get_playlist_as_station(playlist_name=pl_names[int(choice)])
		except Exception as e:
			if self._debug: print(e)
			return None


	def search_stations(self, category, keyword=None):
		try:
			if keyword is None:
				keyword = input("Search {}: ".format(self.CATEGORIES[category]))
			if not keyword.strip():
				raise Exception("No keyword found")
			self.station_list = self.search(keyword.strip(), category=category)
			return self.list_current_stations()
		except Exception as e:
			if self._debug: print(e)
			return None


	def list_current_stations(self):
		try:
			if len(self.station_list)==0:
				raise Exception("No stations found")
			elif len(self.station_list)==1:
				return self.station_list[0]
			for i, s in enumerate(self.station_list):
				print("\t", app_msg_color(str(i)), ")", s.name)

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
				print("\t", app_msg_color(str(i)), ")", s, plen_disp)

			choice = input("Choice: ").strip()
			if not choice or not choice.isnumeric() or int(choice)>=len(pl_names):
				raise Exception("Invalid choice!")
			elif int(choice)==len(pl_names)-1:
				new_pl = input("Name the new playlist: ").strip()
				if new_pl:
					self.store.add_to_playlist(playlist_name=new_pl, track=self.station)
					print(app_msg_color("+ {}".format(new_pl)))
				else:
					if self._debug: print("No playlist name provided!")
			else:
				pl = pl_names[int(choice)]
				self.store.add_to_playlist(playlist_name=pl, track=self.station)
				print(app_msg_color("+ {}".format(pl)))
			self.store.write()

		except Exception as e:
			if self._debug: print(e)


	def get_playlist_as_station(self, playlist_name):
		try:
			pl = self.store.get_playlists()
			pl_dict = {'name': playlist_name, 'track_dict_list': list(pl[playlist_name].values())}
			return Playlist(pl_dict)
		except Exception as e:
			if self._debug: print(e)
			return None


	def playlist_jump_to_track(self):
		try:
			print("Jump to track -")
			for i, t in enumerate(self.station.track_list):
				print("\t", app_msg_color(str(i)), ")", t)

			choice = input("Choice: ").strip()
			if not choice or not choice.isnumeric() or int(choice)>=len(self.station.track_list):
				raise Exception("Invalid choice!")
			else:
				self.station.jump_to(int(choice))
		except Exception as e:
			if self._debug: print(e)


	def get_command(self):
		cmd = getch().lower()
		if isinstance(cmd, bytes): cmd = cmd.decode('utf-8', errors='ignore')
		return (self.CONTROLS.get(cmd) or '').lower()


	def run_cli(self, search_tuple=(None, None)):
		cmd = ''
		new_station = None

		input_category, search_term = search_tuple
		try:
			while True:
				if new_station is not None:
					self.station = new_station
					self.station.stop()
					new_station = None
					continue # This will restart the while loop to make sure everything is set correctly

				if self.station is None:
					new_station = self.station_picker(category=input_category, keyword=search_term)
					if new_station is None:
						# no search results found. clearing input_category and search_term
						input_category = None
						search_term = None
					continue # This will restart the while loop to make sure everything is set correctly

				if not self.station.is_playing() and not self.station.is_paused(): # station is not None
					print(self.station)
					self.station.play()
					self.store.update_last_played(self.station)
					self.store.write()
					continue # This will restart the while loop to make sure everything is set correctly

				while True: # start key-press loop
					self.station.show_time(True)
					cmd = self.get_command()
					wipeline()
					if cmd == '':
						continue

					elif cmd == 'exit':
						raise ExitException("Exit!")

					elif cmd == 'print-current':
						self.station.show_time(False)
						if isinstance(self.station, LiveStation):
							print(self.station)
						else:
							print(self.station.current_track)

					elif cmd == 'change-category':
						self.station.show_time(False)
						new_station = self.station_picker(force=False)
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

					elif cmd == 'jump-to-track': # Only for playlist mode
						self.station.show_time(False)
						self.playlist_jump_to_track()

					elif cmd == 'list-last-search': # No search when in playlists
						self.station.show_time(False)
						new_station = self.list_current_stations()
						break

					elif cmd == 'search-station': # No search when in playlists
						self.station.show_time(False)
						new_station = self.search_stations(category=self.category)
						break

					elif cmd == 'shuffle-playlist-toggle':
						self.station.toggle_shuffle()
						self.station.show_time(False)
						print(app_msg_color("Shuffle on" if self.station.shuffle else "Shuffle off"))

					elif cmd == 'repeat-track-toggle':
						self.station.toggle_repeat()
						self.station.show_time(False)
						print(app_msg_color("Repeat on" if self.station.repeat else "Repeat off"))

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
	parser = argparse.ArgumentParser("iheart")
	parser.add_argument("-v", '--version', help="show version and exit", action="store_true")
	parser.add_argument("-d", '--debug', help="enable debug messages", action="store_true")
	parser.add_argument('--no-color', help="Disable color output", action="store_true")

	group = parser.add_mutually_exclusive_group(required=False)
	group.add_argument("-a", "--artist", help="search Artist radio with provided artist name")
	group.add_argument("-s", "--song", help="search Song radio with provided song name")
	group.add_argument("-l", "--live", help="search Live radio with provided station name")
	group.add_argument("-p", "--playlist", help="play selected local playlist (exact name required)")
	parser.add_argument("--shuffle", help="start playlist in shuffle mode (only works while --playlist is specified)", action='store_true')

	args = parser.parse_args()

	if not vlc_is_installed():
		print("Error: VLC Media Player is required but not installed. Please install it and try again!")
		print("It can be installed from https://www.videolan.org/\n")
		return 1

	if args.version:
		print(__version__)
		return None

	if args.no_color or not Colors.supported():
		Colors.DISABLED = True

	# setup category and search term if provided
	if args.artist is not None:
		category = iHeart.ARTISTS
		search_term = args.artist

	elif args.song is not None:
		category = iHeart.TRACKS
		search_term = args.song

	elif args.live is not None:
		category = iHeart.STATIONS
		search_term = args.live

	elif args.playlist is not None:
		category = iHeart.PLAYLISTS
		search_term = args.playlist

	else:
		category = None
		search_term = None

	configdir = os.path.join(
		os.environ.get('APPDATA') or
		os.environ.get('XDG_CONFIG_HOME') or
		os.path.join(os.environ['HOME'], '.config'),
		"iheartcli"
	)
	if not os.path.isdir(configdir): os.makedirs(configdir)

	try:
		# Welcome message
		print(WELCOME_MSG)
		radio = iHeart_CLI(configdir, debug=args.debug)
		if category == iHeart.PLAYLISTS:
			# set the playlist if name is correct, else will be set to None
			radio.station = radio.get_playlist_as_station(search_term)
			if radio.station is not None and args.shuffle == True:
				radio.station.toggle_shuffle()
		radio.run_cli(search_tuple=(category, search_term))

	except KeyboardInterrupt:
		print("KeyboardInterrupt")
	except ExitException as e:
		print(e)
	except Exception:
		print("error occured. use --debug flag to print error details")
		if args.debug:
			traceback.print_exc()
			# print(e)
		return 1
	return 0



if __name__ == "__main__":
	exit(main())
