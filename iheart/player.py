import sys
import vlc
import time


# Silent install VLC on windows
# certutil.exe -urlcache -split -f "https://get.videolan.org/vlc/3.0.11/win32/vlc-3.0.11-win32.exe" "vlc-3.0.11-win32.exe"
# vlc-3.0.11-win32.exe /L=1033 /S


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
		if self.plr is None:
			return None
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
				event.elapsed = 999
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
			media_list = self.inst.media_list_new()
			media_list.add_media(self.mrl)
			self.plr = self.inst.media_list_player_new()
			self.plr.set_media_list(media_list)
			self.list_player = True
			# print("playing playlist>")
		elif ext == "mp3":
			self.plr = vlc.MediaPlayer(self.mrl) # for some reason some mp3 can't be played with self.inst.media_player_new()
			self.list_player = False
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

	def parse_metadata(self):
		out = {}
		player = self.get_internal_player()
		if player:
			media = player.get_media()
			if not media.is_parsed():
				media.parse_with_options(vlc.MediaParseFlag.local, 100)
			out['now_playing'] = media.get_meta(vlc.Meta.NowPlaying)
			out['title'] = media.get_meta(vlc.Meta.Title)
			out['artist'] = media.get_meta(vlc.Meta.Artist)
			out['duration'] = media.get_meta(vlc.Meta.TrackTotal)
		return out
