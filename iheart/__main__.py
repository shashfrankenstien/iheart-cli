import os, sys
import traceback
from collections import OrderedDict, namedtuple
import json
import argparse


from .stations import (
	iHeartLiveStation,
	iHeartSongStation,
	iHeartArtistStation,
	LocalPlaylist,

	aNONradio,
	InternetRadio
)

from .stations.iheart_radio import client as iheart_client

from .player import vlc_is_installed
from .colors import Colors
from .storage import iRadio_Storage
from .conf import ConfigurationManager
from . import __version__


try:
	from msvcrt import getch
except ImportError:
	import termios
	import tty
	def getch(): # getchar(), getc(stdin)  #PYCHOK flake
		fd = sys.stdin.fileno()
		old = termios.tcgetattr(fd)
		try:
			tty.setraw(fd)
			ch = sys.stdin.read(1)
		finally:
			termios.tcsetattr(fd, termios.TCSADRAIN, old)
			return ch


printjson = lambda j: print(json.dumps(j, indent=4, default=str))
wipeline = lambda:sys.stdout.write("\33[2K\r")
app_msg_color = lambda m: Colors.colorize(m, Colors.YELLOW, bold=False)
app_critical_color = lambda m: Colors.colorize(m, Colors.RED, bold=False)

CategoryControl = namedtuple('CategoryControl', ['name', 'shorthand'])


WELCOME_MSG = '''Welcome to iHeart cli player (v{})!
Type '?' during playback to show available commands.'''.format(__version__)

WELCOME_MSG = app_msg_color(WELCOME_MSG)



def _print_error(msg):
	print(" {} {}".format(
		Colors.colorize("x", Colors.RED, bold=True),
		Colors.colorize(msg, Colors.GRAY, bold=False),
	))





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

	def __init__(self, uuid_filepath):
		self.user = iheart_client.ilogin(uuid_filepath=uuid_filepath)
		self.user_id = self.user['profileId']

	def search(self, keyword, category=None, startIndex=0):
		if category is None: category = self.ARTISTS
		search_res = iheart_client.isearch(keyword, startIndex=startIndex)

		if category==self.STATIONS:
			station_class = iHeartLiveStation
		elif category==self.ARTISTS:
			station_class = iHeartArtistStation
		elif category==self.TRACKS:
			station_class = iHeartSongStation
		else:
			# return search_res['results'][category]
			raise NotImplementedError("'{}' not implemented yet")

		out = []
		for result in search_res['results'][category]:
			result['user_id'] = self.user_id
			out.append(station_class(result))
		return out




class iHeart_CLI(iHeart):

	PLAYLISTS = 'playlists' # this is not iHeart playlists. it is used for local playlists implemented in stations/iheart_radio/playlist.py
	ANON = 'aNONradio'
	INTERNET = 'internet-radio'

	CATEGORIES = OrderedDict({
		iHeart.ARTISTS: CategoryControl('Artist Radio', 'a'),
		iHeart.TRACKS: CategoryControl('Song Radio', 's'),
		iHeart.STATIONS: CategoryControl("Live Radio", 'l'),
		# non-iheart station types
		PLAYLISTS: CategoryControl('Playlists', 'p'),
		ANON: CategoryControl('aNONradio.net', 'n'),
		INTERNET: CategoryControl('internet-radio.com', 'i'),
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

	def __init__(self, config_manager: ConfigurationManager):
		datadir = config_manager.get_datadir()
		uuid_file = os.path.join(datadir, "iheart-api.uuid")
		super().__init__(uuid_filepath=uuid_file)
		self.store = iRadio_Storage(
			config_manager=config_manager,
			supported_stations=[
				iHeartArtistStation,
				iHeartLiveStation,
				iHeartSongStation,
				LocalPlaylist,
				aNONradio,
				InternetRadio,
			]
		)
		self.station_list = []
		self._station = None
		self._debug = os.environ.get('RADIO_DEBUG') == "1"


	def print_help(self):
		wipeline()
		for cmd, action in self.CONTROLS.items():
			if cmd.strip() != '': # ignore the implied controls that cannot be printed
				print("\t", app_msg_color(cmd), "  ", action)

	@property
	def category(self):
		# category getter to convert current station to it's category
		if isinstance(self.station, iHeartLiveStation):
			return self.STATIONS
		# ArtistStation should be checked for after checking for it's subclasses - SongStation and Playlist
		elif isinstance(self.station, iHeartSongStation):
			return self.TRACKS
		elif isinstance(self.station, LocalPlaylist):
			return self.PLAYLISTS
		elif isinstance(self.station, iHeartArtistStation):
			return self.ARTISTS
		elif isinstance(self.station, aNONradio):
			return self.ANON
		elif isinstance(self.station, InternetRadio):
			return self.INTERNET
		else:
			return None


	@property
	def station(self):
		return self._station

	@station.setter
	def station(self, station):
		# Modifying controls based on selected station type
		self.CONTROLS = self.COMMON_CONTROLS.copy()
		if isinstance(station, LocalPlaylist):
			self.CONTROLS['s'] = 'shuffle-playlist-toggle' # No search when in playlists, instead, use 's' for shuffle
			self.CONTROLS['l'] = 'list-playlist-tracks' # List tracks when in playlists
			self.CONTROLS['j'] = 'jump-to-track' # Jump to track by index in playlist
			self.CONTROLS['d'] = 'delete-from-playlist' # Delete track from playlist
		elif isinstance(station, iHeartLiveStation):
			del self.CONTROLS['+'] # Cannot add live stations to playlists
			del self.CONTROLS['r'] # Cannot repeat track in live stations
		elif isinstance(station, (aNONradio, InternetRadio)):
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

		if category == self.INTERNET:
			return InternetRadio()

		elif category == self.PLAYLISTS:
			# highjacking playlist category for Json stored implementation
			return self.choose_playlist()
		else:
			return self.search_stations(category=category, keyword=keyword)


	def choose_category(self, force=True):
		print("Pick a category -")
		pl = self.store.get_playlists()
		playlist_count = len(pl)
		cats_consts = {}
		for c, ctrl in self.CATEGORIES.items():
			if c==self.PLAYLISTS and playlist_count==0:
				continue
			cats_consts[ctrl.shorthand] = c

			print("\t", app_msg_color(str(ctrl.shorthand)), ")", ctrl.name)
		try:
			choice = input("Pick: ").strip()
			if choice == '':
				choice = cats_consts.keys()[0] # default choice
			elif not choice or choice not in cats_consts:
				_print_error("Invalid choice!")
				raise Exception("Invalid choice!")
			return cats_consts[choice]
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
				keyword = input("Search {}: ".format(self.CATEGORIES[category].name))
			if not keyword.strip():
				raise Exception("No keyword provided")
			return self.list_current_stations(getter=lambda startIndex:self.search(keyword.strip(), category=category, startIndex=startIndex))
		except Exception as e:
			if self._debug: print(e)
		return None


	def list_current_stations(self, getter=None):
		'''
		This method takes an input function 'getter'
		- the getter must take start index as argument and return a list of stations.
			this allows for pagination type workflow
		'''
		try:
			new_search = (getter is not None)
			is_playing = self.station is not None and self.station.is_playing()
			if new_search:
				print(app_msg_color("Enter 'm' to list more results."))
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

				choice_msg = "Choice: "
				if not is_playing:
					choice_msg = f"Choice {app_msg_color('(default 0)')}: "
				choice = input(choice_msg).strip()
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
			_print_error(str(e))
			if self._debug:
				traceback.print_exc()


	def delete_from_playlist(self):
		'''deletes current track from playlist'''
		if not isinstance(self.station, LocalPlaylist) or self.station.now_playing_id is None: # only works if current station is a playlist
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
			return LocalPlaylist(pl_dict)
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
					continue # This will restart the while loop to make sure everything is setup correctly

				if self.station is None:
					new_station = self.station_picker(category=input_category, keyword=search_term)
					if new_station is None:
						# no search results found. clearing input_category and search_term
						input_category = None
						search_term = None
					continue # This will restart the while loop to make sure everything is setup correctly

				if not self.station.is_playing() and not self.station.is_paused(): # station is not None
					print(self.station) # NOTE this is the main print statement that is seen on screen
					self.station.on_track_change(self.store.now_playing)
					self.station.play()
					self.store.update_last_played(self.station)
					continue # This will restart the while loop to make sure everything is setup correctly

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
						if hasattr(self.station, 'current_track'):
							print(self.station.current_track)
						else:
							print(self.station)

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
	parser.add_argument("-c", '--config-path', help="show config path and exit", action="store_true")
	parser.add_argument('--no-color', help="disable color output", action="store_true")

	group = parser.add_mutually_exclusive_group(required=False)
	group.add_argument("-a", "--artist", help="search Artist radio with provided artist name")
	group.add_argument("-s", "--song", help="search Song radio with provided song name")
	group.add_argument("-l", "--live", help="search Live radio with provided station name")
	group.add_argument("-p", "--playlist", help="play selected local playlist (exact name required)")
	group.add_argument("-n", "--anon", help="play aNONradio.net", action="store_true")
	group.add_argument("-i", "--internet-radio", help="play internet-radio.com", action="store_true")

	parser.add_argument("--shuffle", help="start playlist in shuffle mode (only works when --playlist is specified)", action='store_true')
	args = parser.parse_args()

	if not vlc_is_installed():
		print("Error: VLC Media Player is required but not installed. Please install it and try again!")
		print("It can be installed from https://www.videolan.org/\n")
		return 1

	if args.debug:
		os.environ['RADIO_DEBUG'] = "1"
	else:
		os.environ['RADIO_DEBUG'] = "0"

	if args.version:
		print(__version__)
		return None

	config_manager = ConfigurationManager()

	if args.config_path:
		print(config_manager.conffile)
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

	elif args.internet_radio is True:
		category = iHeart_CLI.INTERNET
		search_term = None

	else:
		category = None
		search_term = None


	try:
		# Welcome message
		print(WELCOME_MSG)
		radio = iHeart_CLI(config_manager)
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
