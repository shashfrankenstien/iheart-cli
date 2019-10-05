# from playsound import playsound

# import requests

def _playsoundNix(sound, block=True):
	"""Play a sound using GStreamer.

	Inspired by this:
	https://gstreamer.freedesktop.org/documentation/tutorials/playback/playbin-usage.html
	"""
	if not block:
		raise NotImplementedError(
			"block=False cannot be used on this platform yet")

	# pathname2url escapes non-URL-safe characters
	import os
	try:
		from urllib.request import pathname2url
	except ImportError:
		# python 2
		from urllib import pathname2url

	import gi
	gi.require_version('Gst', '1.0')
	from gi.repository import Gst

	Gst.init(None)

	playbin = Gst.ElementFactory.make('playbin', 'playbin')
	if sound.startswith(('http://', 'https://')):
		playbin.props.uri = sound
	else:
		playbin.props.uri = 'file://' + pathname2url(os.path.abspath(sound))

	set_result = playbin.set_state(Gst.State.PLAYING)
	if set_result != Gst.StateChangeReturn.ASYNC:
		raise Exception(
			"playbin.set_state returned " + repr(set_result))

	# FIXME: use some other bus method than poll() with block=False
	# https://lazka.github.io/pgi-docs/#Gst-1.0/classes/Bus.html
	bus = playbin.get_bus()
	print("will poll")
	# bus.add_watch()
	# bus.poll(Gst.MessageType.EOS, Gst.CLOCK_TIME_NONE)
	import time
	time.sleep(3)
	print("done polling")
	playbin.set_state(Gst.State.NULL)



# _playsoundNix('http://c5.prod.playlists.ihrhls.com/1465/playlist.m3u8')
_playsoundNix('test.aac')