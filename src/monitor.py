import logging
import os
import re
import time

from helper.plex import Plex
from helper.trakt import Trakt

# Processed TV Show

show_id = ''
show_name = ''
season_number = ''
episode_number = ''

# Processed Movie

imdb_id = ''
movie_name = ''

# Media common attributes

duration = ''
progress = 0

# Target User ID (will be gone when multiuser gets supported)

USER_ID = '1'

'''
    Keeps an eye on Plex Media Server log
'''


def monitor_log(config):
    logger = logging.getLogger(__name__)
    st_mtime = False

    try:
        f = open(config.get('plex-trakt-scrobbler', 'mediaserver_log_location'))
    except IOError:
        logger.error('Unable to read log-file {0}. Shutting down.'
                     .format(config.get('plex-trakt-scrobbler', 'mediaserver_log_location')))
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
                mtime=time.ctime(os.fstat(f.fileno()).st_mtime)))
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
        # id and send it off to trakt.tv for scrobble.
        if line:
            parse_line(config, line)


'''
    Matches known TV shows metadata log entries entries against input (log_line)

    @param log_line: Plex media server log line
        
    @return Nothing 
'''


def parse_line(config, log_line):
    SCROBBLE_REGEX = [
        re.compile('.*Updated play state for /library/metadata/([0-9]+).*'),
    ]

    WATCHED_REGEX = [
        re.compile('.*Library item ([0-9]+).* got played by account ([0-9]+)!')
    ]

    UNWATCHED_REGEX = [
        re.compile('.*Library item ([0-9]+).* got unplayed by account ([0-9]+)!')
    ]

    for regex in SCROBBLE_REGEX:
        m = regex.match(log_line)

        if m:
            scrobble(config, m.group(1))

    for regex in WATCHED_REGEX:
        m = regex.match(log_line)

        if m:
            mark_as_watched(config, m.group(1), m.group(2))


'''
    Scrobbles a media item against Trakt TV

    @param item: media item ID
        
    @return Nothing 
'''


def scrobble(config, item):
    plex = Plex(config)
    media = plex.get_media_metadata_from_library(item)
    if 'show_id' in media:
        scrobble_show(config, item)
    else:
        scrobble_movie(config, item)


'''
    Scrobbles a TV Show episode item

    @param item: TV Show episode item
        
    @return Nothing 
'''


def scrobble_show(config, item):
    global show_id
    global show_name
    global season_number
    global episode_number
    global duration
    global progress

    logger = logging.getLogger(__name__)

    plex = Plex(config)
    metadata = plex.get_media_metadata_from_sessions(item, USER_ID)

    scrobbling = 'stop'

    if metadata:
        show_id = metadata['show_id']
        show_name = metadata['show_name']
        season_number = metadata['season_number']
        episode_number = metadata['episode_number']
        duration = metadata['duration']
        progress = metadata['progress']
        scrobbling = metadata['srobbling']

    if show_id:
        episode_label = "{0} S{1}E{2} - ({3}) - Progress: {4} - Duration: {5}" \
            .format(show_name, season_number, episode_number, scrobbling, progress, duration)

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


'''
    Scrobbles a Movie item

    @param item: Movie item ID
        
    @return Nothing 
'''


def scrobble_movie(config, item):
    global imdb_id
    global movie_name
    global duration
    global progress

    logger = logging.getLogger(__name__)

    plex = Plex(config)
    metadata = plex.get_media_metadata_from_sessions(item, USER_ID)

    scrobbling = 'stop'

    if metadata:
        imdb_id = metadata['imdb_id']
        movie_name = metadata['movie_name']
        duration = metadata['duration']
        progress = metadata['progress']
        scrobbling = metadata['srobbling']

    if imdb_id:
        movie_label = "{0} - ({1}) - Progress: {2} - Duration: {3}" \
            .format(movie_name, scrobbling, progress, duration)

        logger.info("Scrobble - {0}".format(movie_label))
        trakt = Trakt(config)
        trakt.scrobble_movie(imdb_id, progress, scrobbling)

    if not metadata:
        imdb_id = ''
        movie_name = ''
        duration = ''
        progress = 0


'''
    Marks a media item as watched

    @param item: media item ID

    @return Nothing
'''


def mark_as_watched(config, media_id, user_id):
    if user_id == USER_ID:
        plex = Plex(config)
        media = plex.get_media_metadata_from_library(media_id)
        if 'show_id' in media:
            mark_show_as_watched(config, media_id, user_id)
        else:
            mark_movie_as_watched(config, media_id, user_id)


'''
    Marks a TV Show episode item as watched

    @param item: TV Show episode item

    @return Nothing
'''


def mark_show_as_watched(config, media_id, user_id):
    logger = logging.getLogger(__name__)

    if user_id == USER_ID:
        plex = Plex(config)
        metadata = plex.get_media_metadata_from_library(media_id)
        if not metadata: return

        episode_label = "{0} S{1}E{2}" \
            .format(metadata['show_name'], metadata['season_number'], metadata['episode_number'])
        logger.info("Mark as watched - {0}".format(episode_label))

        trakt = Trakt(config)
        trakt.scrobble_show(metadata['show_name'], metadata['season_number'], metadata['episode_number'], 100, 'stop')


'''
    Marks a Movie item as watched

    @param item: Movie item ID

    @return Nothing
'''


def mark_movie_as_watched(config, media_id, user_id):
    logger = logging.getLogger(__name__)

    if user_id == USER_ID:
        plex = Plex(config)
        metadata = plex.get_media_metadata_from_library(media_id)
        if not metadata: return

        logger.info("Mark as watched - {0}".format(metadata['movie_name']))

        trakt = Trakt(config)
        trakt.scrobble_movie(metadata['imdb_id'], 100, 'stop')
