import requests
import uuid
import os

new_user_url = 'https://us.api.iheart.com/api/v1/account/loginOrCreateOauthUser'
markets_url = 'https://us.api.iheart.com/api/v2/content/markets?countryCode=US&limit=1&cache=true&zipCode={zipCode}'
search_url = 'https://us.api.iheart.com/api/v3/search/all'

#stations
station_stream_url = 'https://us.api.iheart.com/api/v2/content/liveStations/{stream_id}'
meta_url = 'https://us.api.iheart.com/api/v3/live-meta/stream/{stream_id}/currentTrackMeta'


artist_url = 'https://us.api.iheart.com/api/v1/catalog/getArtistByArtistId?artistId={artist_id}' #GET
artist_profile_url = 'https://us.api.iheart.com/api/v3/artists/profiles/{artist_id}' #GET
similar_artists_url = 'https://us.api.iheart.com/api/v1/catalog/artist/{artist_id}/getSimilar' #GET
artist_albums_url = 'https://us.api.iheart.com/api/v3/catalog/artist/{artist_id}/albums' #GET

artist_playlist_url = 'https://us.api.iheart.com/api/v2/playlists/{user_id}/ARTIST/{artist_id}' #POST formData = {'contentId':artist_id, 'playedFrom':10}
artist_stream_url = 'https://us.api.iheart.com/api/v2/playback/streams' # Takes steramId in POST params


#NOTE useful track info - No stream available
track_url = 'https://us.api.iheart.com/api/v1/catalog/getTrackByTrackId?trackId={track_id}' #GET
track2_url = 'https://us.api.iheart.com/api/v3/catalog/tracks/{track_id}' #GET



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
	# "Connection": "keep-alive"
}



def _generic_get(url):
	res = requests.get(url, headers=HEADERS)
	try:
		return res.json()
	except:
		raise Exception(res.text)


# **************************************************************************************
# ********************************** API Functions *************************************
# **************************************************************************************


def ilogin(uuid_filepath):
	global HEADERS
	accessToken = 'anon'
	uu = ''
	if os.path.isfile(uuid_filepath):
		with open(uuid_filepath, 'r') as u:
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
	try:
		with open(uuid_filepath, 'w') as u:
			u.write(uu)
		user = res.json()
		HEADERS.update({
			'X-Ihr-Profile-Id': str(user['profileId']),
			'X-Ihr-Session-Id': user['sessionId'],
			'X-User-Id': str(user['profileId']),
			'X-Session-Id': user['sessionId'],
		})
		return user
	except:
		raise Exception(res.text)


def iget_market_id(zipCode):
	res = requests.get(markets_url.format(zipCode=zipCode), headers=HEADERS).json()['hits']
	if len(res)==0:
		raise Exception("Unsupported zipCode")


def isearch(keyword, startIndex=0, maxRows=10, marketId=159):
	res = requests.get(search_url, params={
		'boostMarketId': marketId,
		'startIndex':startIndex,
		'maxRows':maxRows,
		'keyword':True,
		'keywords': keyword,
	}, headers=HEADERS)
	return res.json()


def iget_station_streams(stream_id):
	if isinstance(stream_id, (list, set)):
		stream_id = ','.join(stream_id)
	res = requests.get(station_stream_url.format(stream_id=stream_id), headers=HEADERS).json()
	if 'hits' in res:
		return res['hits'][0].get("streams") or {}
	else:
		raise Exception(str(res))

def iget_live_meta(stream_id):
	return _generic_get(meta_url.format(stream_id=stream_id))


def iget_artist_profile(artist_id):
	return _generic_get(artist_profile_url.format(artist_id=artist_id))

def iget_artist_bio(artist_id):
	return _generic_get(artist_url.format(artist_id=artist_id))


def iget_artist_station(user_id, artist_id):
	res = requests.post(
		artist_playlist_url.format(user_id=user_id, artist_id=artist_id),
		data={'contentId':artist_id},
		headers=HEADERS
	)
	try:
		res_json = res.json()
		if 'error' in res_json:
			raise Exception(str(res_json['error']))
		return res_json
	except:
		raise Exception(res.text)


def iget_artist_streams(astream_id):
	res = requests.post(artist_stream_url, json={
		'hostName': 'webapp.US',
		'playedFrom': 1,
		'stationId': astream_id,
		'stationType': 'RADIO'
	}, headers=HEADERS)
	try:
		res_json = res.json()
		if 'error' in res_json:
			raise Exception(str(res_json['error']))
		return res_json.get('items') or []
	except:
		raise Exception(res.text)


def iget_track_info(track_id):
	return _generic_get(track_url.format(track_id=track_id))
