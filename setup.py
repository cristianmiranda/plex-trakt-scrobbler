import os
from distutils.core import setup

NAME = 'plex-trakt-scrobbler'
VERSION = '1.1.0'

setup(
    name = 'plex_trakt_scrobbler',
    version = VERSION,
    author = 'Cristian Miranda',
    author_email = 'crism60@gmail.com',
    description = ('Scrobble TV shows played via Plex Media Center'),
    license = 'MIT',
    url = 'https://github.com/cristianmiranda/plex-trakt-scrobbler',
    scripts = ['scripts/plex-trakt-scrobbler.py'],
    packages=['plex_trakt_scrobbler'],
    data_files = [(
      os.path.expanduser('~/.config/{0}'.format(NAME)),
      ['conf/plex_trakt_scrobbler.conf'],
      )]
)
