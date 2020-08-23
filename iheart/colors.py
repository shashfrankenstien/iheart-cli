import os, sys
import random

class Colors(object):
	RED = 31
	GREEN = 32
	YELLOW = 93#33
	BLUE = 34
	PINK = 35
	LIGHT_BLUE = 36
	WHITE = 37
	GRAY = 90
	CYAN = 96

	DISABLED = False

	@staticmethod
	def colorize(message, color, bold=False):
		if Colors.DISABLED:
			return message
		else:
			if isinstance(color, list):
				color = random.choice(color)
			color_code = '{};{}'.format(1 if bold else 0, color)
			return "\033[{}m".format(color_code)+message+"\033[0m"


	@staticmethod
	def supported():
		"""
		Return True if the running system's terminal supports color,
		and False otherwise.
		"""
		supported_platform = sys.platform != 'win32' or 'ANSICON' in os.environ

		# isatty is not always implemented, #6223.
		is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
		return supported_platform and is_a_tty
