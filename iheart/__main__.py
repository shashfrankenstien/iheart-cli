import os, sys
import termios
import traceback
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




def search_stations(radio, keyword=None):
	if keyword is None:
		keyword = input("Search for station: ")
	if not keyword.strip():
		return None
	station_list = radio.search(keyword.strip(), category=radio.ARTISTS)

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
				station = search_stations(radio=radio, keyword=search_term)
				new_station = None
				continue

			elif not station.is_playing() and not station.is_paused(): # station is not None
				station.play()

			print(station)

			while True:
				cmd = getch().strip().lower()
				sys.stdout.write("\r")
				if cmd == 'q':
					raise Exception("Exit!")
				if cmd == 'p':
					if station.is_playing():
						station.toggle_pause(True)
						print("paused")
					else:
						station.toggle_pause(False)
				elif cmd == 'l':
					new_station = search_stations(radio=radio, keyword=station.search_term)
					break
				elif cmd == 's':
					new_station = search_stations(radio=radio, keyword=None)
					break
				elif cmd == 'i':
					print(station.info())
				elif cmd == 'n':
					station.forward()
		except:
			traceback.print_exc()
			break
	if station is not None: station.stop()




if __name__ == "__main__":
	main()