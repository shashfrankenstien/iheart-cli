import os, sys
import traceback
from collections import OrderedDict
import json
import argparse


from .stations import (
	Station, # base class
	LiveStation,
	SongStation,
	ArtistStation,
	Playlist,

	aNONradio
)

from .stations.iheart_radio import client as iheart_client

from .player import vlc_is_installed
from .colors import Colors
from . import __version__


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
app_critical_color = lambda m: Colors.colorize(m, Colors.RED, bold=False)


WELCOME_MSG = '''Welcome to iHeart cli player (v{})!
Type '?' during playback to show available commands.'''.format(__version__)

WELCOME_MSG = app_msg_color(WELCOME_MSG)


CONFIGDIR = os.path.join(
	os.environ.get('APPDATA') or
	os.environ.get('XDG_CONFIG_HOME') or
	os.path.join(os.environ['HOME'], '.config'),
	"iheartcli"
)
if not os.path.isdir(CONFIGDIR): os.makedirs(CONFIGDIR)


def _print_error(msg):
	print(" {} {}".format(
		Colors.colorize("x", Colors.RED, bold=True),
		Colors.colorize(msg, Colors.GRAY, bold=False),
	))



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

		Playlist.__name__: Playlist,
		aNONradio.__name__: aNONradio,
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
		self.write()

	def add_to_playlist(self, playlist_name, track):
		if not isinstance(track, dict):
			track = self.current_track_to_dict(track)
		if playlist_name not in self.DATA['playlists']:
			self.DATA['playlists'][playlist_name] = OrderedDict()
		track_id = str(track['__id__']) # json.dump automatically converts keys to strings. make it explicit!
		if track_id not in self.DATA['playlists'][playlist_name]:
			self.DATA['playlists'][playlist_name][track_id] = track #__id__ is unique iheart id
		self.write()

	def delete_from_playlist_by_id(self, playlist_name, track_id):
		track_id = str(track_id) # json.dump automatically converts keys to strings. make it explicit!
		if playlist_name in self.DATA['playlists'] and track_id in self.DATA['playlists'][playlist_name]:
			del self.DATA['playlists'][playlist_name][track_id]
			self.write()

	def get_playlists(self):
		return self.DATA['playlists']




class ExitException(Exception):
	pass




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

	def __init__(self, uuid_filepath, print_url=False):
		self.user = iheart_client.ilogin(uuid_filepath=uuid_filepath)
		self.user_id = self.user['profileId']
		global PRINT_PLAYING_URL
		PRINT_PLAYING_URL = print_url

	def search(self, keyword, category=None, startIndex=0):
		if category is None: category = self.ARTISTS
		search_res = iheart_client.isearch(keyword, startIndex=startIndex)

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




class iHeart_CLI(iHeart):

	PLAYLISTS = 'playlists' # this is not iHeart playlists. it is used for local playlists implemented in __main__.py
	ANON = 'aNONradio'

	CATEGORIES = OrderedDict({
		iHeart.ARTISTS: 'Artist Radio',
		iHeart.TRACKS: 'Song Radio',
		iHeart.STATIONS: "Live Radio",
		# non-iheart station types
		PLAYLISTS: 'Playlists',
		ANON: 'aNONradio.net',
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
		super().__init__(uuid_filepath=uuid_file, print_url=False)
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
			return self.STATIONS
		# ArtistStation should be checked for after checking for it's subclasses - SongStation and Playlist
		elif isinstance(self.station, SongStation):
			return self.TRACKS
		elif isinstance(self.station, Playlist):
			return self.PLAYLISTS
		elif isinstance(self.station, ArtistStation):
			return self.ARTISTS
		elif isinstance(self.station, aNONradio):
			return self.ANON
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
			self.CONTROLS['d'] = 'delete-from-playlist' # Delete track from playlist
		elif isinstance(station, LiveStation):
			del self.CONTROLS['+'] # Cannot add live stations to playlists
			del self.CONTROLS['r'] # Cannot repeat track in live stations
		elif isinstance(station, aNONradio):
			del self.CONTROLS['+'] # Cannot add live stations to playlists
			del self.CONTROLS['r'] # Cannot repeat track in aNONradio stations
			del self.CONTROLS['s'] # Cannot search track in aNONradio stations
			del self.CONTROLS['l'] # Cannot list last search in aNONradio stations
			del self.CONTROLS['n'] # Cannot forward / go next in aNONradio stations

		self.CONTROLS.move_to_end('q') # make exit / quit the last option
		self._station = station


	def station_picker(self, category=None, keyword=None, force=True):
		# wrapper to pick category and accordingly select station
		if category is None:
			category = self.choose_category(force=force)

		if category == self.ANON:
			return aNONradio()

		elif category == self.PLAYLISTS:
			# highjacking playlist category for Json stored implementation
			return self.choose_playlist()
		else:
			return self.search_stations(category=category, keyword=keyword)


	def choose_category(self, force=True):
		print("Pick a category -")
		pl = self.store.get_playlists()
		playlist_count = len(pl)
		cat_names = []
		cats_consts = []
		for c in self.CATEGORIES:
			if c==self.PLAYLISTS and playlist_count==0:
				continue
			cats_consts.append(c)
			cat_names.append(self.CATEGORIES[c])

		for i, s in enumerate(cat_names):
			print("\t", app_msg_color(str(i)), ")", s)
		try:
			choice = input("Pick: ").strip()
			if choice == '':
				choice = 0 # default choice
			elif not choice or not choice.isnumeric() or int(choice)>=len(cat_names):
				_print_error("Invalid choice!")
				raise Exception("Invalid choice!")
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
			if choice == '':
				choice = 0 # default choice
			elif not choice or not choice.isnumeric() or int(choice)>=len(pl_names):
				_print_error("Invalid choice!")
				raise Exception("Invalid choice!")
			return self.get_playlist_as_station(playlist_name=pl_names[int(choice)])
		except Exception as e:
			if self._debug: print(e)
			return None


	def search_stations(self, category, keyword=None):
		try:
			if keyword is None:
				keyword = input("Search {}: ".format(self.CATEGORIES[category]))
			if not keyword.strip():
				raise Exception("No keyword provided")
			return self.list_current_stations(getter=lambda startIndex:self.search(keyword.strip(), category=category, startIndex=startIndex))
		except Exception as e:
			if self._debug: print(e)
		return None


	def list_current_stations(self, getter=None):
		try:
			new_search = (getter is not None)
			is_playing = self.station is not None and self.station.is_playing()
			if new_search:
				msg = "Enter 'm' to list more results."
				if not is_playing:
					msg += "\nPress Enter key to select choice 0."
				print(app_msg_color(msg))
				self.station_list = []

			while True:
				cur_st_len = len(self.station_list)
				if new_search:
					to_print = getter(cur_st_len)
					self.station_list += to_print
				else:
					if cur_st_len==0:
						_print_error("Nothing found")
						raise Exception("Nothing found")
					elif cur_st_len==1:
						return self.station_list[0]
					to_print = self.station_list

				for i, s in enumerate(to_print):
					idx = i
					if new_search:
						idx += cur_st_len
					print("\t", app_msg_color(str(idx)), ")", s.name)

				choice = input("Choice: ").strip()
				if choice == '' and not is_playing:
					choice = 0 # default choice if not playing anything
				elif choice == 'm' and new_search:
					continue # calls getter again
				elif not choice or not choice.isnumeric() or int(choice)>=len(self.station_list):
					_print_error("Invalid choice!")
					raise Exception("Invalid choice!")
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
				_print_error("Invalid choice!")
				raise Exception("Invalid choice!")
			elif int(choice)==len(pl_names)-1:
				new_pl = input("Name the new playlist: ").strip()
				if new_pl:
					self.store.add_to_playlist(playlist_name=new_pl, track=self.station)
					print(app_msg_color("+ {}".format(new_pl)))
				else:
					_print_error("No playlist name provided!")
			else:
				pl = pl_names[int(choice)]
				self.store.add_to_playlist(playlist_name=pl, track=self.station)
				print(app_msg_color("+ {}".format(pl)))

		except Exception as e:
			if self._debug: print(e)


	def delete_from_playlist(self):
		'''deletes current track from playlist'''
		if not isinstance(self.station, Playlist) or self.station.now_playing_id is None: # only works if current station is a playlist
			return None
		try:
			choice = input(app_msg_color(f"Delete current track from '{self.station.name}'? (y/n): ")).strip()
			if choice not in ('y','n'):
				_print_error("Invalid choice!")
				return None

			if choice == 'y':
				print(app_critical_color("- {}".format(self.station.name)))
				cur_track_id = self.station.now_playing_id
				self.station.forward() # first move to next track since we'll be deleting current track
				self.store.delete_from_playlist_by_id(playlist_name=self.station.name, track_id=cur_track_id)
				self.station.remove_track(cur_track_id)
		except Exception as e:
			if self._debug: print(e)
		return None


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
			if choice == '':
				choice = 0 # default choice
			elif not choice or not choice.isnumeric() or int(choice)>=len(self.station.track_list):
				_print_error("Invalid choice!")
				raise Exception("Invalid choice!")
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
						if isinstance(self.station, (LiveStation, aNONradio)):
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

					elif cmd == 'delete-from-playlist':
						self.station.show_time(False)
						self.delete_from_playlist()
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
	group.add_argument("--anon", help="play aNONradio.net", action="store_true")

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
		category = iHeart_CLI.ARTISTS
		search_term = args.artist

	elif args.song is not None:
		category = iHeart_CLI.TRACKS
		search_term = args.song

	elif args.live is not None:
		category = iHeart_CLI.STATIONS
		search_term = args.live

	elif args.playlist is not None:
		category = iHeart_CLI.PLAYLISTS
		search_term = args.playlist

	elif args.anon is True:
		category = iHeart_CLI.ANON
		search_term = None

	else:
		category = None
		search_term = None


	try:
		# Welcome message
		print(WELCOME_MSG)
		radio = iHeart_CLI(CONFIGDIR, debug=args.debug)
		if category == iHeart_CLI.PLAYLISTS:
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
