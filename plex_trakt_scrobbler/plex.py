import socket
import urllib2
import urllib
import urlparse
import xml.etree.ElementTree as ET
import re
from htmlentitydefs import name2codepoint
import hashlib
import sys
import logging
import time
import os
import json

'''
    This is a helper class to provide assistance with all Plex API calls
'''
class Plex(object):

    def __init__(self, cfg):

        self.logger = logging.getLogger(__name__)
        self.cfg = cfg


    '''
        Get TV Show Episode metadata from Plex users playing sessions.
        
        @param l_id     : Episode TVDB id
        @param user_id  : Plex user id

        @return         : TV Show episode metadata
    '''
    def get_show_episode_metadata_from_sessions(self, l_id, user_id):

        url = '{url}/status/sessions?X-Plex-Token={plex_token}'.format(url=self.cfg.get('plex-trakt-scrobbler',
          'mediaserver_url'), plex_token=self.cfg.get('plex-trakt-scrobbler','plex_token'))
        self.logger.info('Fetching sessions status from {url}'.format(url=url))
    
        try:
            metadata = urllib2.urlopen(url, timeout=2)
        except urllib2.URLError, e:
            logger.error('urllib2 error reading from {url} \'{error}\''.format(url=url, error=e))
            return None
        except socket.timeout, e:
            logger.error('Timeout reading from {url} \'{error}\''.format(url=url, error=e))
            return None

        tree = ET.fromstring(metadata.read())
        videos = tree.findall('Video')

        if videos is None:
            logger.error('No videos found in sessions status feed.')
        else:
            for video in videos:
                user = video.find('User')
                if user.get('id') != user_id:
                    self.logger.info('Ignoring played item library-id={l_id}, because it is from another user.'.
                        format(l_id=l_id))
                    continue

                if video.get('type') != 'episode':
                    self.logger.info('Ignoring played item library-id={l_id}, because it is not an episode.'.
                        format(l_id=l_id))
                    return None

                transcode = video.find('TranscodeSession')
                if transcode is None:
                    self.logger.info('Ignoring played item library-id={l_id}, could not determine transcoding information.'.
                        format(l_id=l_id))
                    return None

                player = video.find('Player')
                if player is None:
                    self.logger.info('Ignoring played item library-id={l_id}, could not determine player information.'.
                        format(l_id=l_id))
                    return None

                episode = video.get('guid')
                regex = re.compile('com.plexapp.agents.thetvdb://([0-9]+)/([0-9]+)/([0-9]+)\?.*')
                m = regex.match(episode)

                if m:
                    played_time = video.get('viewOffset')
                    duration = transcode.get('duration')
                    state = player.get('state')
                    progress = long(float(played_time)) * 100 / long(float(duration))

                    return {
                        'show_id': m.group(1),
                        'show_name': video.get('grandparentTitle'),
                        'season_number': m.group(2),
                        'episode_number': m.group(3),
                        'duration': duration,
                        'progress': progress,
                        'srobbling' : 'start' if state == 'playing' else 'pause'
                    }

                else:
                    return None
        
        return None


    '''
        Get TV Show Episode metadata from Plex library.
        
        @param l_id     : Episode TVDB id

        @return         : TV Show episode metadata
    '''
    def get_show_episode_metadata_from_library(self, l_id):

        url = '{url}/library/metadata/{l_id}?X-Plex-Token={plex_token}'.format(url=self.cfg.get('plex-trakt-scrobbler',
          'mediaserver_url'), l_id=l_id, plex_token=self.cfg.get('plex-trakt-scrobbler','plex_token'))
        self.logger.info('Fetching library metadata from {url}'.format(url=url))
        
        try:
            metadata = urllib2.urlopen(url, timeout=2)
        except urllib2.URLError, e:
            self.logger.error('urllib2 error reading from {url} \'{error}\''.format(url=url,
                          error=e))
            return None
        except socket.timeout, e:
            self.logger.error('Timeout reading from {url} \'{error}\''.format(url=url, error=e))
            return None

        tree = ET.fromstring(metadata.read())
        video = tree.find('Video')

        if video is None:
            self.ogger.info('Ignoring played item library-id={l_id}, could not determine video library information.'.
                    format(l_id=l_id))
            return None

        if video.get('type') != 'episode':
            self.logger.info('Ignoring played item library-id={l_id}, because it is not an episode.'.
                    format(l_id=l_id))
            return None

        # matching from the guid field, which should provide the agent TVDB result
        episode = video.get('guid')
        show_name = video.get('grandparentTitle')

        regex = re.compile('com.plexapp.agents.thetvdb://([0-9]+)/([0-9]+)/([0-9]+)\?.*')
        m = regex.match(episode)

        if not m:
            return None

        return {
            'show_id': m.group(1),
            'show_name': show_name,
            'season_number': m.group(2),
            'episode_number': m.group(3)
        }
