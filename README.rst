iHeart Radio
================

Command line client for `iHeartRadio <https://www.iheart.com/>`_

|Python 3.6| |license|


This project is meant to be a learning exercise. It is heavily inspired by `pianobar <https://github.com/PromyLOPh/pianobar>`_ which I love!

The project is a cross platform iHeartRadio console client implemented in Python. It is simply an alternative to playing iHeartRadio on the browser; only plays Live and Artist radio stations which are available without needing to create an account.

Features
---------------------

* Play Live and Artist radio stations
* Play Song radio stations (Which are essentially Artist stations, but created using song names)
* Save song urls into local playlists maintained as json files

    - Each playlist is saved as a separate json file and can be freely copied between machines
    - Play songs in a playlist sequentially or on shuffle

* Play `aNONradio <https://anonradio.net/>`_

Dependencies
---------------------

This project does not implement an audio player. It uses VLC for cross platform audio playback. It can be installed from the `VLC website <https://www.videolan.org>`_


Installation/Usage
---------------------

Using pip - `Great read <https://matthew-brett.github.io/pydagogue/installing_scripts.html>`_

.. code::

    $ pip install -U iheart-cli
    $ iheart


From repository

.. code::

    $ git clone https://github.com/shashfrankenstien/iheart-cli.git
    $ cd iHeart-cli
    $ python3 -m pip install .
    $ iheart


View command line options help

.. code:: shell

    $ iheart --help


TODO
---------------------

* Improve messages while in use
* Add tests


.. |Python 3.6| image:: https://img.shields.io/badge/python-3.6+-blue.svg
.. |license| image:: https://img.shields.io/github/license/shashfrankenstien/iheart-cli
