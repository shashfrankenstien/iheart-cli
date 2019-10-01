import os, sys
import traceback
from collections import OrderedDict
import json

from iheart import iHeart


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

class ExitException(Exception):
	pass




class iheart_cli(iHeart):

	CATEGORIES = {
		"Live Radio": iHeart.STATIONS,
		'Artist Radio': iHeart.ARTISTS,
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
		self.configdir = configdir
		uuid_file = os.path.join(self.configdir, "iheart-cli.uuid")
		super().__init__(uuid_store=uuid_file)
		self._debug = debug
		self._category = category or iHeart.ARTISTS
		self.station_list = []
		self.station = None

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
							print("paused")
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
		radio = iheart_cli(configdir)
		radio.choose_category()
		radio.run_cli(search_term)
	except KeyboardInterrupt:
		print("KeyboardInterrupt")
	except Exception as e:
		print(e)



if __name__ == "__main__":
	main()