import os
os.environ['RADIO_DEBUG'] = "1"
import time
import json
printjson = lambda j: print(json.dumps(j, indent=4, default=str))


from iheart.player import VLCPlayer
from iheart.__main__ import iHeart
from iheart.stations.iheart_radio import client as iheart_client

from iheart.stations import aNONradio, InternetRadio


IHEART_UUID_FILE = "test.uuid"

def teardown_function(function):
	if os.path.isfile(IHEART_UUID_FILE):
		os.remove(IHEART_UUID_FILE)




def test_player():
	url = 'http://custom-hls.iheart.com/bell-ingestion-pipeline-production-umg/encodes/Dec18/121218/full/00602537937011_20181206002655653/00602537937011_T55_audtrk.m4a.m3u8?null'
	player = VLCPlayer.get_player(url)
	player.play()
	print('''<Track: "Bad Medicine" by "Bon Jovi" on "Bon Jovi">''')
	time.sleep(5)
	player.stop()


def test_iheart_search():
	res = iheart_client.isearch("Bob")
	assert('results' in res)


def test_iheart_live_stations():
	radio = iHeart(IHEART_UUID_FILE)
	res = radio.search("Rock", category=iHeart.STATIONS)
	for station in res[:2]:
		station.play()
		printjson(station.get_dict())
		time.sleep(5)
		station.stop()
		time.sleep(2)


def test_iheart_artist_radio():
	artist_keyword = "Queen" # = input("Search for artist: ")
	radio = iHeart(IHEART_UUID_FILE)
	res = radio.search(artist_keyword, category=iHeart.ARTISTS)
	for station in res[:2]:
		station.play()
		printjson(station.get_dict())
		time.sleep(5)
		station.stop()
		time.sleep(1)
	# printjson({'a': artist.get_current_track().get_dict()})

def test_iheart_song_radio():
	track_name = "wild world"
	radio = iHeart(IHEART_UUID_FILE)
	res = radio.search(track_name, category=iHeart.TRACKS)
	for station in res[:2]:
		print(station)
		printjson(station.get_dict())
		station.play()
		time.sleep(5)
		station.stop()



def test_anon_radio():
	radio = aNONradio()
	printjson(radio.get_dict())
	radio.play()
	time.sleep(60) # unfortunately, this is very slow :(
	radio.stop()


def test_internet_radio():
	radio = InternetRadio()
	printjson(radio.get_dict())
	radio.play()
	time.sleep(60) # unfortunately, this is very slow :(
	radio.stop()

