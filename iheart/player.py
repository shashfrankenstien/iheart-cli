import requests
import time
import os, sys
import vlc

def get_urls(txt):
	return [k.strip() for k in txt.split("\n") if k.strip().startswith("http")]

inst = vlc.Instance("--adaptive-use-access")

st = time.time()
while time.time()-st < 5:
	r = requests.get("http://c5.prod.playlists.ihrhls.com/1465/playlist.m3u8")

	nu = get_urls(r.text)[0]
	r = requests.get(nu)

	streams = get_urls(r.text)
	plr = inst.media_list_player_new()
	ml = inst.media_list_new()


	for s in streams:
		ml.add_media(s)
	plr.set_media_list(ml)
	plr.play()
	t = 0
	time.sleep(1)
	while plr.is_playing():
		time.sleep(1)
		t = t+1
		sys.stdout.write("\r\t{}".format(t))

	time.sleep(1)

