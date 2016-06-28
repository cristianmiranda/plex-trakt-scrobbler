#!/usr/bin/env python
import re
import os
import socket
import urllib2
import xml.etree.ElementTree as ET
import logging
import time

from trakt import Trakt

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

    logger = logging.getLogger(__name__)

    metadata = fetch_metadata_from_sessions(item, config)
    if not metadata: return
    
    episode_label = "{0} S{1}E{2} - ({3}) - Progress: {4} - Duration: {5}".format(metadata['show_name'],
                                                      metadata['season_number'],
                                                      metadata['episode_number'],
                                                      metadata['srobbling'],
                                                      metadata['progress'],
                                                      metadata['duration'])

    logger.info("Scrobble - {0}".format(episode_label))

    # submit to tvshowtime.com
    trakt = Trakt(config)
    a = trakt.scrobble_show(metadata['show_name'], 
        metadata['season_number'], 
        metadata['episode_number'], 
        metadata['progress'], 
        metadata['srobbling'])


def watch(config, item):
    ''' Processes played / unplayed item scrobbling TVShowTime

        :param item: played / unplayed item id
        :type item: integer 
        :param played: flag to know if item has been played or unplayed
        :type played: boolean '''

    logger = logging.getLogger(__name__)

    metadata = fetch_metadata_from_library(item, config)
    if not metadata: return
    
    episode_label = "{0} S{1}E{2}".format(metadata['show_name'], metadata['season_number'], metadata['episode_number'])
    logger.info("Watch -  {0}".format(episode_label))

    # submit to tvshowtime.com
    trakt = Trakt(config)
    a = trakt.scrobble_show(metadata['show_name'], 
        metadata['season_number'], 
        metadata['episode_number'], 
        100, 
        'stop')


def fetch_metadata_from_sessions(l_id, config):
    global show_id
    global show_name
    global season_number
    global episode_number
    global duration
    global progress

    logger = logging.getLogger(__name__)

    url = '{url}/status/sessions?X-Plex-Token={plex_token}'.format(url=config.get('plex-trakt-scrobbler',
      'mediaserver_url'), plex_token=config.get('plex-trakt-scrobbler','plex_token'))
    logger.info('Fetching sessions status from {url}'.format(url=url))

    # fail if request is greater than 2 seconds.
    try:
        metadata = urllib2.urlopen(url, timeout=2)
    except urllib2.URLError, e:
        logger.error('urllib2 error reading from {url} \'{error}\''.format(url=url,
                      error=e))
        return False
    except socket.timeout, e:
        logger.error('Timeout reading from {url} \'{error}\''.format(url=url, error=e))
        return False

    tree = ET.fromstring(metadata.read())
    videos = tree.findall('Video')


    if videos is not None:
        for video in videos:
            user = video.find('User')
            if user.get('id') != '1':
                logger.info('Ignoring played item library-id={l_id}, because it from another user.'.
                    format(l_id=l_id))
                continue

            if video.get('type') != 'episode':
                logger.info('Ignoring played item library-id={l_id}, because it is not an episode.'.
                    format(l_id=l_id))
                return False

            transcode = video.find('TranscodeSession')
            if transcode is None:
                logger.info('Ignoring played item library-id={l_id}, could not determine transcoding information.'.
                    format(l_id=l_id))
                return False


            player = video.find('Player')
            if player is None:
                logger.info('Ignoring played item library-id={l_id}, could not determine player information.'.
                    format(l_id=l_id))
                return False

            # matching from the guid field, which should provide the agent TVDB result
            episode = video.get('guid')
            show_name = video.get('grandparentTitle')
            duration = transcode.get('duration')
            played_time = video.get('viewOffset')
            state = player.get('state')
            progress = long(float(played_time)) * 100 / long(float(duration))

            regex = re.compile('com.plexapp.agents.thetvdb://([0-9]+)/([0-9]+)/([0-9]+)\?.*')
            m = regex.match(episode)

            if m:
                show_id = m.group(1)
                season_number = m.group(2)
                episode_number = m.group(3)

                return {
                    'show_id': show_id,
                    'show_name': show_name,
                    'season_number': season_number,
                    'episode_number': episode_number,
                    'duration': duration,
                    'progress': progress,
                    'srobbling' : 'start' if state == 'playing' else 'pause'
                }

            else:
                return False
    else:
        logger.error('No videos found in sessions status feed.')
    
    if show_id != '':
        result = {
            'show_id': show_id,
            'show_name': show_name,
            'season_number': season_number,
            'episode_number': episode_number,
            'duration': duration,
            'progress': progress,
            'srobbling' : 'stop'
        }

        show_id = ''
        show_name = ''
        season_number = ''
        episode_number = ''
        duration = ''
        progress = 0

        return result

    return False


def fetch_metadata_from_library(l_id, config):
    ''' retrieves the metadata information from the Plex media Server api. '''

    logger = logging.getLogger(__name__)
    url = '{url}/library/metadata/{l_id}?X-Plex-Token={plex_token}'.format(url=config.get('plex-trakt-scrobbler',
      'mediaserver_url'), l_id=l_id, plex_token=config.get('plex-trakt-scrobbler','plex_token'))
    logger.info('Fetching library metadata from {url}'.format(url=url))

    # fail if request is greater than 2 seconds.
    try:
        metadata = urllib2.urlopen(url, timeout=2)
    except urllib2.URLError, e:
        logger.error('urllib2 error reading from {url} \'{error}\''.format(url=url,
                      error=e))
        return False
    except socket.timeout, e:
        logger.error('Timeout reading from {url} \'{error}\''.format(url=url, error=e))
        return False

    tree = ET.fromstring(metadata.read())
    video = tree.find('Video')

    if video is None:
        logger.info('Ignoring played item library-id={l_id}, could not determine video library information.'.
                format(l_id=l_id))
        return False

    if video.get('type') != 'episode':
        logger.info('Ignoring played item library-id={l_id}, because it is not an episode.'.
                format(l_id=l_id))
        return False

    # matching from the guid field, which should provide the agent TVDB result
    episode = video.get('guid')
    show_name = video.get('grandparentTitle')

    regex = re.compile('com.plexapp.agents.thetvdb://([0-9]+)/([0-9]+)/([0-9]+)\?.*')
    m = regex.match(episode)

    if not m:
        return False

    return {
        'show_id': m.group(1),
        'show_name': show_name,
        'season_number': m.group(2),
        'episode_number': m.group(3)
    }


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
