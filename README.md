# iHeart Radio
> Command line client for iHeartRadio

![Python 3.6](https://img.shields.io/badge/python-3.6+-blue.svg)

This project started off as a learning exercise. It is heavily inspired by [pianobar](https://github.com/PromyLOPh/pianobar) which I love!

It implements a cross platform iHeartRadio console client in Python, only plays Live and Artist radio stations which are available without needing to create an account.

## Features

* Play Live and Artist radio stations
* Play Song radio stations (Which are essentially Artist stations, but created using song names)
* Save songs into local playlists maintained as json files
    - Each playlist is saved as a separate json file and can be freely copied between machines
    - Play songs in a playlist sequentially or on shuffle

## Dependencies

This project does not implement a player. It uses VLC for cross platform audio playback. It can be installed from the [VLC website](https://www.videolan.org)


## Installation/Usage
```shell
$ git clone https://github.com/shashfrankenstien/iHeart-cli.git
$ cd iHeart-cli
$ python3 -m iheart
```

## TODO

* Improve messages while in use
* Show a meaningful message if VLC is not installed
* Add tests
* Make it installable, probably through pip - [Great read](https://matthew-brett.github.io/pydagogue/installing_scripts.html)
