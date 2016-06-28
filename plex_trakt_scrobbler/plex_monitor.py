#!/usr/bin/env python
import re
import os
import socket
import urllib2
import xml.etree.ElementTree as ET
import logging
import time

from trak import Trak

last_played = None
last_unplayed = None

def parse_line(config, log_line):
    ''' Matches known TV shows metadata log entries entries against input (log_line)

        :param log_line: plex media server log line
        :type log_line: string
        :returns: Nothing '''

    logger = logging.getLogger(__name__)

    PLAYED_REGEX = [
        re.compile('.*Updated play state for /library/metadata/([0-9]+).*'),
        re.compile('.*Library item ([0-9]+).* got played by account')
    ]

    UNPLAYED_REGEX = [
        re.compile('.*Library item ([0-9]+).* got unplayed by account')
    ]

    for regex in PLAYED_REGEX:
        m = regex.match(log_line)

        if m:
            logger.info('Found played TV show and extracted library id \'{l_id}\' from plex log '.format(l_id=m.group(1)))
            process_item(config, m.group(1), True)

    for regex in UNPLAYED_REGEX:
        m = regex.match(log_line)

        if m:
            logger.info('Found unplayed TV show and extracted library id \'{l_id}\' from plex log '.format(l_id=m.group(1)))
            process_item(config, m.group(1), False)


def process_item(config, item, played):
    ''' Processes played / unplayed item scrobbling TVShowTime

        :param item: played / unplayed item id
        :type item: integer 
        :param played: flag to know if item has been played or unplayed
        :type played: boolean '''

    global last_played
    global last_unplayed
    logger = logging.getLogger(__name__)

    # when playing via a client, log lines are duplicated (seen via iOS)
    # this skips dupes. Note: will also miss songs that have been repeated
    if (played and item == last_played) or (not played and item == last_unplayed):
        logger.warn('Dupe detection : {0}, not submitting'.format(item))
        return

    metadata = fetch_metadata(item, config)

    if not metadata: return

    # submit to tvshowtime.com
    tvst = Trak(config)
    a = tvst.scrobble(metadata['show_id'], metadata['season_number'],
            metadata['number'], played)

    # scrobble was not successful , FIXME: do something?
    # if not a:

    if played:
        last_played = item
    else:
        last_unplayed = item


def fetch_metadata(l_id, config):
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

    print video

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

    if m:
        episode_label = "{0} S{1}E{2}".format(show_name,
                                              m.group(2).zfill(2),
                                              m.group(3).zfill(2))
        logger.info("Matched TV show {0}".format(episode_label))
    else:
        return False

    return {
        'show_id': m.group(1),
        'season_number': m.group(2),
        'number': m.group(3)
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

        time.sleep(.03)

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
