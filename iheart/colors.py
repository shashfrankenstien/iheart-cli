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

	@staticmethod
	def colorize(message, color, bold=False):
		if isinstance(color, list):
			color = random.choice(color)
		color_code = '{};{}'.format(1 if bold else 0, color)
		# return "\u001b[{}m".format(color_code)+message+"\u001b[0m"
		return "\033[{}m".format(color_code)+message+"\033[0m"
