import requests
import uuid
import vlc
import json
import time
import os


# Install VLC on windows
# certutil.exe -urlcache -split -f "https://get.videolan.org/vlc/3.0.8/win32/vlc-3.0.8-win32.exe" "vlc-3.0.8-win32.exe"
# vlc-3.0.8-win32.exe /L=1033 /S


new_user_url = 'https://us.api.iheart.com/api/v1/account/loginOrCreateOauthUser'
markets_url = 'https://us.api.iheart.com/api/v2/content/markets?countryCode=US&limit=1&cache=true&zipCode={}'
search_url = 'https://us.api.iheart.com/api/v3/search/all'
stream_url = 'https://us.api.iheart.com/api/v2/content/liveStations/{}'
meta_url = 'https://us.api.iheart.com/api/v3/live-meta/stream/{}/currentTrackMeta'



HEADERS = {
	"Host": "us.api.iheart.com",
	"User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:68.0) Gecko/20100101 Firefox/68.0",
	"Accept": "application/json, text/plain, */*",
	"Accept-Language": "en-US,en;q=0.5",
	"Accept-Encoding": "gzip, deflate, br",
	"Referer": "https://www.iheart.com/",
	"X-hostName": "webapp.US",
	"X-Locale": "en-US",
	"Origin": "https://www.iheart.com",
	"DNT": "1",
	"Connection": "keep-alive"
}

CWD = os.path.dirname(os.path.realpath(__file__))
UUID_STORE = os.path.join(CWD, "iheart.uuid")

printjson = lambda j: print(json.dumps(j, indent=4))


def login():
	global HEADERS
	accessToken = 'anon'
	uu = ''
	if os.path.isfile(UUID_STORE):
		with open(UUID_STORE, 'r') as u:
			uu = u.read()
	if not uu:
		uu = str(uuid.uuid1())
	body = {
		'acessToken': accessToken,
		'accessTokenType': accessToken,
		'deviceId': uu,
		'deviceName': 'python-CLI',
		'host': 'webapp.US',
		'oauthUuid': uu,
		'userName': accessToken+uu
	}
	res = requests.post(new_user_url, data=body, headers=HEADERS)
	if res.status_code == 200:
		with open(UUID_STORE, 'w') as u:
			u.write(uu)
		user = res.json()
		HEADERS.update({
			'X-Ihr-Profile-Id': str(user['profileId']),
			'X-Ihr-Session-Id': user['sessionId'],
			'X-User-Id': str(user['profileId']),
			'X-Session-Id': user['sessionId'],
		})
		return user
	else:
		raise Exception(res.text)


def market_id(zipCode='11211'):
	return requests.get(markets_url.format(zipCode), headers=HEADERS).json()['hits'][0]


def search(keyword, marketId=159):
	res = requests.get(search_url, params={
		'boostMarketId': marketId,
		'bundle':True,
		'keyword':True,
		'keywords': keyword,
	})
	return res.json()

def get_stream(stream_id):
	res = requests.get(stream_url.format(stream_id)).json()
	if 'hits' in res:
		return res['hits'][0]
	else:
		raise Exception(str(res))

def get_meta(stream_id):
	res = requests.get(meta_url.format(stream_id), headers=HEADERS)
	try:
		return res.json()
	except:
		raise Exception(res.text)

def play(mrl, t=20):
	inst = vlc.Instance("--adaptive-use-access") # Create a VLC instance
	p = inst.media_player_new() # Create a player instance
	# cmd1 = "sout=file/ts:%s" % outfile
	media = inst.media_new(mrl)
	print(media.parse_with_options(1, timeout=20*1000))
	print(media.get_mrl())
	p.set_media(media)
	p.play()

	st = time.time()
	while time.time()-st < t:
		print(time.time()-st)
		time.sleep(1)
	p.stop()
	p.release()
	inst.release()



if __name__ == "__main__":

	print(login())
	search_res = search("Classic Rock")
	printjson(search_res)

	first_station = search_res['results']['stations'][0]
	stream = get_stream(first_station['id'])

	print("============================")
	printjson(stream)

	play(stream['streams']['hls_stream'], t=30)

	print(get_meta(first_station['id']))

