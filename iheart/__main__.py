import os, sys
import traceback
from collections import OrderedDict
import json

from iheart import iHeart
from iheart import ArtistStation, LiveStation, SongStation, Station
from iheart import Track


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



class iHeart_Storage(object):

	DATA = {
		'last_station': None,
	}

	def __init__(self, configdir):
		self.configdir = configdir

	@staticmethod
	def station_to_dict(station_instance):
		d = station_instance.get_dict()
		d['__name__'] = station_instance.__class__.__name__

	@staticmethod
	def station_from_dict(self, d):
		if '__name__' not in d:
			raise Exception("Not a Track/Station dict")
		elif d['__name__']==ArtistStation.__name__:
			return ArtistStation(d)
		elif d['__name__']==LiveStation.__name__:
			return LiveStation(d)
		elif d['__name__']==Station.__name__:
			return Station(d)
		else:
			raise Exception("Not a Track/Station dict")

	def current_track_to_dict(self, station_instance):
		if isinstance(station_instance, (ArtistStation, SongStation)):
			track = station_instance.get_current_track()
			if track:
				return self.station_to_dict(track)
			else:
				return {}
		else:
			return self.station_to_dict(station_instance)


class ExitException(Exception):
	pass

class iHeart_CLI(iHeart):

	CATEGORIES = {
		"Live Radio": iHeart.STATIONS,
		'Artist Radio': iHeart.ARTISTS,
		'Song Radio': iHeart.TRACKS,
	}

	CONTROLS = OrderedDict({
		'?': 'help',
		'p': 'pause-play',
		'n': 'next',
		'i': 'information',
		'l': 'list-last-search',
		's': 'search-stations',
		'q': 'exit',
	})


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

	def choose_category(self):
		print("Pick a category -")
		cats = sorted(list(self.CATEGORIES.keys()))
		for i, s in enumerate(cats):
			print("\t", i, ")", s)
		try:
			choice = input("Pick: ").strip()
			if not choice or not choice.isnumeric() or int(choice)>=len(cats):
				raise Exception("Invalid choice!")
			else:
				self._category = self.CATEGORIES[cats[int(choice)]]
		except Exception as e:
			if self._debug: print(e)
			self.choose_category()

	def search_stations(self, keyword=None):
		try:
			if keyword is None:
				keyword = input("Search for station: ")
			if not keyword.strip():
				raise Exception("No keyword found")
			self.station_list = self.search(keyword.strip(), category=self._category)
			return self.list_current_stations()
		except Exception as e:
			self._debug: print(e)
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
			self._debug: print(e)
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
					self.station = self.search_stations(keyword=search_term)
					new_station = None
					continue

				elif not self.station.is_playing() and not self.station.is_paused(): # station is not None
					print(self.station)
					self.station.play()

				self.station.show_time(True)
				while True:
					cmd = self.get_command()
					wipeline()
					if cmd == 'exit':
						raise ExitException("Exit!")
					if cmd == 'pause-play':
						if self.station.is_playing():
							self.station.toggle_pause(True)
							sys.stdout.write("paused\r")
						else:
							self.station.toggle_pause(False)

					elif cmd == 'list-last-search':
						self.station.show_time(False)
						new_station = self.list_current_stations()
						break
					elif cmd == 'search-stations':
						self.station.show_time(False)
						new_station = self.search_stations()
						break
					elif cmd == 'information':
						printjson(self.station.info())
					elif cmd == 'next':
						self.station.forward()
					elif cmd == 'help':
						self.print_help()
		except:
			self._debug: traceback.print_exc()
			raise
		finally:
			if self.station is not None:
				self.station.stop()
				self.station = None




def main():
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
		radio = iHeart_CLI(configdir)
		radio.choose_category()
		radio.run_cli(search_term)
	except KeyboardInterrupt:
		print("KeyboardInterrupt")
	except Exception as e:
		print(e)



if __name__ == "__main__":
	main()
