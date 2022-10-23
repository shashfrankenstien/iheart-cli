import random
from collections import deque

from .base import TrackListStation, Track
from iheart.colors import Colors


class LocalPlaylist(TrackListStation):
	'''Json stored playlist implementation using TrackListStation class'''

	def __init__(self, playlist_dict):
		playlist_dict['id'] = playlist_dict['name']
		super().__init__(playlist_dict)
		self.track_list = deque([Track(trk_dict) for trk_dict in playlist_dict['track_dict_list']]) # deque so as to use rotate
		self.tracks_to_play = self.track_list.copy() # make copy to implement shuffle
		self.shuffle = False
		self.now_playing_id = None

	def __str__(self):
		return "<Playlist: {}> {}".format(
			Colors.colorize(self.id, Colors.CYAN),
			Colors.colorize("[Shuffle]", Colors.PINK) if self.shuffle else '',
		)

	def iter_tracks(self):
		while True:
			new_track = self.tracks_to_play[0]
			self.now_playing_id = new_track.id
			yield new_track
			self.tracks_to_play.rotate(-1) # rotate left to go to next track

	def remove_track(self, track_id):
		def filter_func(t):
			return t.id != track_id
		self.track_list = deque(filter(filter_func, self.track_list))
		self.tracks_to_play = deque(filter(filter_func, self.tracks_to_play))

	def toggle_shuffle(self):
		self.shuffle = not self.shuffle
		if self.shuffle:
			random.shuffle(self.tracks_to_play) # shuffle playlist
		else: # shuffle off
			# if there is a song playing in shuffle mode,
			# rotate tracklist such that the playlist continues from the current track
			current_idx = 0
			if self.now_playing_id is not None:
				for i, t in enumerate(self.track_list):
					if t.id==self.now_playing_id:
						current_idx = i
						break

			self.tracks_to_play = self.track_list.copy() # make copy of original track list
			self.tracks_to_play.rotate(-1*current_idx) # rotate left to current track

	def jump_to(self, idx):
		if idx < len(self.track_list):
			track = self.track_list[idx]
			for i, t in enumerate(self.tracks_to_play):
				if t.id==track.id:
					self.tracks_to_play.rotate(-1*(i-1)) # rotate left so that selected track will play next
					self.forward() # then trigger jump to next song
					break

