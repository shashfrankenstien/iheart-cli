import requests
from bs4 import BeautifulSoup

base_url = "https://www.internet-radio.com"

all_stations_url = "https://www.internet-radio.com/stations/"

station_url = "https://www.internet-radio.com/stations/{station}/"
search_url = "https://www.internet-radio.com/search/?radio={searchTerm}"


HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:105.0) Gecko/20100101 Firefox/105.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1"
}


def ir_get_stations():
    res = requests.get(all_stations_url, headers=HEADERS)
    soup = BeautifulSoup(res.content, 'lxml')
    stations = []
    for elem in soup.find_all(attrs={'class':'text-capitalize'}):
        stations.append(elem.text)
    return stations


def _ir_find_actual_url(search_term):
    stations = ir_get_stations()
    search_term = search_term.strip().lower()
    if search_term in stations:
        return station_url.format(station=search_term)
    else:
        search_term = '+'.join(search_term.split())
        return search_url.format(searchTerm=search_term)


def _ir_parse_meta(meta_txt):
    meta = {}
    for m in str(meta_txt).split('\n'):
        m = m.strip().lower()
        for key in ['kbps', 'listeners']:
            if key in m:
                meta[key] = int(m.replace(key, ''))
    return meta

def ir_search(term, maxRows=10, sortby="listeners"):
    if sortby not in ['featured', 'listeners', 'bitrate']:
        raise ValueError(f"invalid value for sortby - {sortby}")
    out = []
    page_url = _ir_find_actual_url(search_term=term)
    sess = requests.Session()
    sess.cookies.set("sortby", sortby)

    while len(out) < maxRows:
        res = sess.get(page_url, headers=HEADERS)
        soup = BeautifulSoup(res.content, 'lxml')
        table = soup.find('table')
        rows = table.find_all('tr')

        for tr in rows:
            url = base_url+tr.find('a', attrs={'title':'M3U Playlist File'})['href']
            radio_name = tr.find('h4', attrs={'class':'text-danger'})
            if radio_name.text.strip()=="":
                continue

            meta = _ir_parse_meta(tr.find('td', {'class':'text-right'}).text)

            resdict = {
                'id': hash(url),
                'user_id': 'anonymous',
                'name': radio_name.text.strip(),
                'current_track': radio_name.parent.find('b').text.strip(),
                'mrl': url,
            }
            resdict.update(meta)
            out.append(resdict)

        next_btn = soup.find('li', attrs={'class':'next'})
        if not next_btn:
            break
        page_url = base_url+next_btn.find('a')['href']

    return out[:maxRows]


if __name__ == '__main__':
    out = ir_search("bob")

    print(len(out))
    # import json
    # print(json.dumps(out, indent=4))
