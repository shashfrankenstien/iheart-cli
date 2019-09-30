import os, sys
import traceback
from collections import OrderedDict
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

class InvisibilityCloak(object):

	def __enter__(self):
		self.fd = sys.stdin.fileno()
		self.old = termios.tcgetattr(self.fd)
		self.new = termios.tcgetattr(self.fd)
		self.new[3] = self.new[3] & ~termios.ECHO          # lflags
		termios.tcsetattr(self.fd, termios.TCSADRAIN, self.new)

	def __exit__(self, *args):
		termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old)


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

def print_help():
	for cmd, action in CONTROLS.items():
		print("\t", cmd, "  ", action)


def choose_category(cats):
	cats = sorted(list(cats))
	for i, s in enumerate(cats):
		print("\t", i, ")", s)
	try:
		choice = input("Pick category: ").strip()
		if not choice:
			return None
		else:
			return cats[int(choice)]
	except Exception as e:
		print(e)
		return None


def search_stations(radio, keyword=None, category=None):
	if keyword is None:
		keyword = input("Search for station: ")
	if not keyword.strip():
		return None
	category = category or radio.STATIONS
	station_list = radio.search(keyword.strip(), category=category)

	if len(station_list)==0:
		return None
	for i, s in enumerate(station_list):
		print("\t", i, ")", s.name)

	try:
		choice = input("Choice: ").strip()
		if not choice:
			return None
		else:
			return station_list[int(choice)]
	except Exception as e:
		print(e)
		return None


class ExitException(Exception):
	pass


def main():
	configdir = os.path.join(
		os.environ.get('APPDATA') or
		os.environ.get('XDG_CONFIG_HOME') or
		os.path.join(os.environ['HOME'], '.config'),
		"iheartcli"
	)

	if not os.path.isdir(configdir): os.makedirs(configdir)
	UUID_STORE = os.path.join(configdir, "iheart-cli.uuid")

	radio = iHeart(UUID_STORE)
	# print(radio.user)

	if len(sys.argv) > 1:
		search_term = sys.argv[1].strip()
	else:
		search_term = None

	categ_choice = choose_category(CATEGORIES.keys())
	category_chosen = CATEGORIES[categ_choice]

	cmd = ''
	station = None
	new_station = None
	while True:
		try:
			if new_station is not None:
				station = new_station
				station.stop()
				new_station = None
				continue

			elif station is None:
				station = search_stations(radio=radio, keyword=search_term, category=category_chosen)
				new_station = None
				continue

			elif not station.is_playing() and not station.is_paused(): # station is not None
				print(station)
				station.play()

			while True:
				cmd = getch().strip().lower()
				if isinstance(cmd, bytes): cmd = cmd.decode('utf-8', errors='ignore')
				cmd = (CONTROLS.get(cmd) or '').lower()
				sys.stdout.write("\r")
				if cmd == 'exit':
					raise ExitException("Exit!")
				if cmd == 'pause-play':
					if station.is_playing():
						station.toggle_pause(True)
						# print("paused")
					else:
						station.toggle_pause(False)
				elif cmd == 'list-last-search':
					new_station = search_stations(radio=radio, keyword=station.search_term, category=category_chosen)
					break
				elif cmd == 'search-stations':
					new_station = search_stations(radio=radio, keyword=None, category=category_chosen)
					break
				elif cmd == 'information':
					print(station.info())
				elif cmd == 'next':
					station.forward()
				elif cmd == 'help':
					print_help()
		except ExitException as e:
			print(e)
			break
		except:
			traceback.print_exc()
			break
	if station is not None: station.stop()




if __name__ == "__main__":
	main()