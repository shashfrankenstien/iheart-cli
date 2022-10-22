import sys
import vlc
import time

from .colors import Colors



# Silent install VLC on windows
# certutil.exe -urlcache -split -f "https://get.videolan.org/vlc/3.0.11/win32/vlc-3.0.11-win32.exe" "vlc-3.0.11-win32.exe"
# vlc-3.0.11-win32.exe /L=1033 /S


PRINT_PLAYING_URL = False

VLC_INSTANCE_FLAGS = "--network-caching=50000 --adaptive-use-access"
if sys.platform.startswith('linux'):
	VLC_INSTANCE_FLAGS += " --aout alsa"


def vlc_is_installed() -> bool:
	try:
		i = vlc.Instance(VLC_INSTANCE_FLAGS) # Create a VLC instance
		i.release()
		return True
	except NameError:
		return False


# **************************************************************************************
# ********************************** Player Classes ************************************
# **************************************************************************************


class VLCPlayer(object):
	'''https://www.olivieraubert.net/vlc/python-ctypes/doc/'''

	POSITION_CHANGED = vlc.EventType.MediaPlayerPositionChanged
	END_REACHED = vlc.EventType.MediaPlayerEndReached
	_PLAYER = None

	def __init__(self, mrl):
		self.mrl = mrl
		self.inst = None
		self.plr = None
		self.list_player = False
		self._paused = False
		self._manager = None
		self._events_registry = {}

		self._play_start_time = None
		self._paused_at = None
		self._total_paused_time = 0

	@classmethod
	def get_player(cls, mrl):
		if cls._PLAYER is None:
			cls._PLAYER = cls(mrl)
		elif mrl!=cls._PLAYER.mrl:
			cls._PLAYER.stop()
			cls._PLAYER = cls(mrl)
		return cls._PLAYER

	def get_internal_player(self):
		if self.list_player:
			return self.plr.get_media_player()
		else:
			return self.plr

	def register_event(self, event_type, callback):
		def _callback_wrapper(event):
			# add event.elapsed - time since play was called
			if self._play_start_time is not None:
				event.elapsed = time.time() - self._play_start_time - self._total_paused_time
			else:
				event.elapsed = None
			callback(event)
		if self._manager is not None:
			self._manager.event_attach(event_type, _callback_wrapper)
		else:
			self._events_registry[event_type] = _callback_wrapper

	def remove_event(self, event_type):
		if self._manager is not None:
			self._manager.event_detach(event_type)
		if event_type in self._events_registry:
			del self._events_registry[event_type]

	def play(self):
		self.stop()
		self.inst = vlc.Instance(VLC_INSTANCE_FLAGS) # Create a VLC instance
		self.inst.log_unset()
		ext = (self.mrl.rpartition(".")[2])[:3]
		if ext in ['pls', 'm3u']:
			media_list = self.inst.media_list_new([self.mrl])
			self.plr = self.inst.media_list_player_new()
			self.plr.set_media_list(media_list)
			self.list_player = True
			# print("playing playlist>")
		else:
			media = self.inst.media_new(self.mrl)
			self.plr = self.inst.media_player_new()
			self.plr.set_media(media)
			self.list_player = False
			# print("playing>")

		self._play_start_time = time.time()
		self._manager = self.get_internal_player().event_manager()
		# apply cached events that were registered before _manager was created
		for evt, cb in self._events_registry.items():
			self.register_event(evt, cb)
		self._events_registry = {}
		self.plr.play()

	def is_playing(self):
		return self.plr is not None and self.plr.is_playing()

	def is_paused(self):
		return self._paused

	def stop(self):
		if self.plr is not None:
			if not self.plr.get_state() in (vlc.State.Ended, vlc.State.Stopped):
				self.plr.stop()
			self.plr.release()
			self.plr = None
		if self.inst is not None:
			self.inst.release()
			self.inst = None
		self._manager = None
		self._play_start_time = None
		self._paused_at = None
		self._total_paused_time = 0

	def forward(self):
		"""Go forward 10 secs"""
		player = self.get_internal_player()
		player.set_time(player.get_time() + 10000)

	def rewind(self):
		"""Go back 10 secs"""
		player = self.get_internal_player()
		player.set_time(player.get_time() - 10000)

	def toggle_pause(self, pause=True):
		self.plr.set_pause(1 if pause else 0)
		self._paused = pause
		if pause is True:
			self._paused_at = time.time()
		elif self._paused_at is not None:
			self._total_paused_time += time.time() - self._paused_at
		time.sleep(0.1)
		return self.is_playing()
		# return self.plr.get_state()




class Track(object):
	# store a class level current playing MRL.
	# - check against this to identify if track is being repeated
	CURRENT_PLAYING_MRL = ''

	def __init__(self, track_dict):
		if 'streamUrl' not in track_dict:
			raise Exception("stream not found")
		self.__dict = track_dict
		self.mrl = track_dict['streamUrl'].replace("https", 'http')

		content = track_dict['content']
		self.id = content['id']
		self.name = content.get('title')
		self.version = content.get('version')
		self.artist = content.get('artistName')
		self.artist_id = content.get('artistId')
		self.album = content.get('albumName')
		self.album_id = content.get('albumId')
		self.lyrics_id = content.get('lyricsId')
		self.imageUrl = content.get('imagePath')

		self.length = content.get('duration')
		self.minutes = self.length // 60
		self.seconds = self.length % 60

		self._on_complete_cb = lambda event:None
		self.__show_time = True

	def get_dict(self):
		return self.__dict

	def __str__(self):
		s = '''Track: "{}" by "{}" on "{}"'''.format(
			Colors.colorize(self.name, Colors.YELLOW, bold=True),
			Colors.colorize(self.artist, Colors.LIGHT_BLUE, bold=True),
			Colors.colorize(self.album, Colors.GREEN, bold=True),
		)
		if self.version:
			s += " [" + Colors.colorize(self.version, Colors.RED, bold=True) + "]"
		s += Colors.colorize(f" ({self.minutes}:{self.seconds:02d})", Colors.GRAY) # add song duration
		return s

	def __repr__(self):
		return str(self)

	def show_time(self, show=True):
		self.__show_time = show

	def _print_remaining_duration(self, event):
		if self.__show_time:
			remaining = int(self.length - event.elapsed)
			m = remaining // 60
			s = (remaining % 60)
			countdown = f"\t-{m:02d}:{s:02d}/{self.minutes:02d}:{self.seconds:02d}\r"
			sys.stdout.write(Colors.colorize(countdown, Colors.WHITE, bold=True))

	def play(self, on_complete):
		self._on_complete_cb = on_complete
		if self.mrl != self.CURRENT_PLAYING_MRL:
			# only print now playing track name if the new track is different
			if PRINT_PLAYING_URL: sys.stdout.write(Colors.colorize(self.mrl, Colors.GRAY) + "\n\r")
			sys.stdout.write(Colors.colorize("( Now Playing ) ", Colors.GRAY, bold=True) + str(self) + "\n\r")
		player = VLCPlayer.get_player(self.mrl)
		player.stop()
		player.register_event(player.END_REACHED, self._on_complete_cb)
		player.register_event(player.POSITION_CHANGED, self._print_remaining_duration)
		self.CURRENT_PLAYING_MRL = self.mrl # register class level current playing mrl
		player.play()

	def force_end(self):
		player = VLCPlayer.get_player(self.mrl)
		player.stop() # calling .stop() is not required here, but it makes sense and doesn't hurt
		self._on_complete_cb(None)

