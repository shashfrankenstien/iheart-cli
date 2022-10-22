import time
import json
printjson = lambda j: print(json.dumps(j, indent=4))


from iheart.player import VLCPlayer
from iheart.__main__ import iHeart


def test_player():
	url = 'http://custom-hls.iheart.com/bell-ingestion-pipeline-production-umg/encodes/Dec18/121218/full/00602537937011_20181206002655653/00602537937011_T55_audtrk.m4a.m3u8?null'
	player = VLCPlayer.get_player(url)
	player.play()
	print('''<Track: "Bad Medicine" by "Bon Jovi" on "Bon Jovi">''')
	time.sleep(5)
	player.stop()


def test_stations():
	radio = iHeart("uu.uuid")
	res = radio.search("Classic Rock", category=iHeart.STATIONS)
	for station in res[:2]:
		station.play()
		time.sleep(5)
		station.stop()
		time.sleep(2)


def test_artist_radio():
	artist_keyword = "Queen" # = input("Search for artist: ")
	radio = iHeart("uu.uuid")
	artist = radio.search(artist_keyword, category=iHeart.ARTISTS)[0]
	print(artist)
	printjson(artist.get_dict())
	artist.play()
	time.sleep(5)
	artist.stop()
	# printjson({'a': artist.get_current_track().get_dict()})

def test_track_search():
	track_name = "wild world"
	radio = iHeart("uu.uuid")
	res1 = radio.search(track_name, category=iHeart.TRACKS)[0]
	print(res1)
	printjson(res1.get_dict())
	res1.play()
	time.sleep(5)
	res1.stop()
	# printjson({'a': res1.get_current_track().get_dict()})

	# printjson(iget_track_info(res1['id']))
