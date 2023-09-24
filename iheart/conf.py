import os
import configparser



DATADIR = os.path.join(
	os.environ.get('APPDATA') or
	os.environ.get('XDG_DATA_HOME') or
	os.path.join(os.environ['HOME'], '.local', 'share'),
	"iheartcli"
)

CONFIGDIR = os.path.join(
	os.environ.get('XDG_CONFIG_HOME') or
	os.path.join(os.environ['HOME'], '.config'),
	"iheartcli"
)
if not os.path.isdir(CONFIGDIR):
	os.makedirs(CONFIGDIR)



class ConfigurationManager:

	def __init__(self) -> None:
		self.configdir = CONFIGDIR
		self.conffile = os.path.join(CONFIGDIR, 'iheartcli.ini')
		self.conf = configparser.ConfigParser()
		self.conf.read(self.conffile)

		if 'datadir' not in self.conf['DEFAULT']:
			self.conf['DEFAULT']['datadir'] = DATADIR
			if not os.path.isdir(DATADIR):
				os.makedirs(DATADIR)

		self.write()


	def write(self):
		with open(self.conffile, 'w') as c:
			self.conf.write(c)


	def add_config(self, key, value):
		self.conf['DEFAULT'][str(key)] = value
		self.write()


	def get_datadir(self):
		return self.conf['DEFAULT']['datadir']

	def _get_value(self, key, default):
		if key in self.conf['DEFAULT']:
			return self.conf['DEFAULT'][key]
		else:
			self.conf['DEFAULT'][key] = str(default)
			self.write()
			return default

	def get_str(self, key, default):
		return str(self._get_value(key, default))

	def get_int(self, key, default):
		return int(self._get_value(key, default))


	def get_bool(self, key, default):
		if key in self.conf['DEFAULT']:
			return self.conf['DEFAULT'].getboolean(key)
		else:
			self.conf['DEFAULT'][key] = 'true' if default else 'false'
			self.write()
			return default
