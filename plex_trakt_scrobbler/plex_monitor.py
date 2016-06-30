#!/usr/bin/env python
import re
import os
import socket
import urllib2
import logging
import time

from trakt import Trakt
from plex import Plex

show_id = ''
show_name = ''
season_number = ''
episode_number = ''
duration = ''
progress = 0

def parse_line(config, log_line):
    ''' Matches known TV shows metadata log entries entries against input (log_line)

        :param log_line: plex media server log line
        :type log_line: string
        :returns: Nothing '''

    logger = logging.getLogger(__name__)

    SCROBBLE_REGEX = [
        re.compile('.*Updated play state for /library/metadata/([0-9]+).*'),
    ]

    WATCHED_REGEX = [
        re.compile('.*Library item ([0-9]+).* got played by account 1!')
    ]

    UNWATCHED_REGEX = [
        re.compile('.*Library item ([0-9]+).* got unplayed by account 1!')
    ]

    for regex in SCROBBLE_REGEX:
        m = regex.match(log_line)

        if m:
            scrobble(config, m.group(1))

    for regex in WATCHED_REGEX:
        m = regex.match(log_line)

        if m:
            watch(config, m.group(1))

    for regex in UNWATCHED_REGEX:
        m = regex.match(log_line)

        #if m:
        # TODO: Remove Watch History


def scrobble(config, item):
    ''' Processes played / unplayed item scrobbling TVShowTime

        :param item: played / unplayed item id
        :type item: integer 
        :param played: flag to know if item has been played or unplayed
        :type played: boolean '''

    global show_id
    global show_name
    global season_number
    global episode_number
    global duration
    global progress

    logger = logging.getLogger(__name__)

    plex = Plex(config)
    metadata = plex.get_show_episode_metadata_from_sessions(item, '1')
    
    scrobbling = 'stop'

    if metadata: 
        show_id = metadata['show_id']
        show_name = metadata['show_name']
        season_number = metadata['season_number']
        episode_number = metadata['episode_number']
        duration = metadata['duration']
        progress = metadata['progress']
        scrobbling = metadata['srobbling']
    
    if show_id != '':
        # submit to tvshowtime.com
        episode_label = "{0} S{1}E{2} - ({3}) - Progress: {4} - Duration: {5}".format(show_name,
                                                      season_number,
                                                      episode_number,
                                                      scrobbling,
                                                      progress,
                                                      duration)

        logger.info("Scrobble - {0}".format(episode_label))
        trakt = Trakt(config)
        trakt.scrobble_show(show_name, season_number, episode_number, progress, scrobbling)

    if not metadata:
        show_id = ''
        show_name = ''
        season_number = ''
        episode_number = ''
        duration = ''
        progress = 0


def watch(config, item):
    logger = logging.getLogger(__name__)

    plex = Plex(config)
    metadata = plex.get_show_episode_metadata_from_library(item)
    if not metadata: return
    
    episode_label = "{0} S{1}E{2}".format(metadata['show_name'], metadata['season_number'], metadata['episode_number'])
    logger.info("Watch -  {0}".format(episode_label))

    # submit to tvshowtime.com
    trakt = Trakt(config)
    a = trakt.scrobble_show(metadata['show_name'], metadata['season_number'], metadata['episode_number'], 100, 'stop')


def monitor_log(config):

    logger = logging.getLogger(__name__)
    st_mtime = False

    try:
        f = open(config.get('plex-trakt-scrobbler', 'mediaserver_log_location'))
    except IOError:
        logger.error('Unable to read log-file {0}. Shutting down.'.format(config.get(
          'plex-trakt-scrobbler', 'mediaserver_log_location')))
        return
    f.seek(0, 2)

    while True:

        time.sleep(0.05)

        # reset our file handle in the event the log file was not written to
        # within the last 60 seconds. This is a very crude attempt to support
        # the log file i/o rotation detection cross-platform.
        if int(time.time()) - int(os.fstat(f.fileno()).st_mtime) >= 60:

            if int(os.fstat(f.fileno()).st_mtime) == st_mtime: continue

            logger.debug('Possible log file rotation, resetting file handle (st_mtime={mtime})'.format(
                mtime=time.ctime(os.fstat(f.fileno()).st_mtime) ))
            f.close()

            try:
                f = open(config.get('plex-trakt-scrobbler', 'mediaserver_log_location'))
            except IOError:
                logger.error('Unable to read log-file {0}. Shutting down.'.format(config.get(
                  'plex-trakt-scrobbler', 'mediaserver_log_location')))
                return

            f.seek(0, 2)
            st_mtime = int(os.fstat(f.fileno()).st_mtime)

        line = f.readline()

        # read all new lines starting at the end. We attempt to match
        # based on a regex value. If we have a match, extract the media file
        # id and send it off to tvshowtime.com for scrobble.
        if line:
            parse_line(config, line)
