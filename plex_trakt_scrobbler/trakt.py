import json
import logging
import os
import socket
import urllib
import urllib2
import urlparse


class Trakt(object):

    CLIENT_ID = 'aa9cd9a641758c5c20f2076e657a199925a6d2409dcddd0c8737b0dc1e90b6b0'
    CLIENT_SECRET = 'c6a1b1d563a521b4b126efd8847cd18d2a5533a702997f6401dd6e8f48c83faa'
    USER_AGENT = 'plex-trakt-scrobbler'

    def __init__(self, cfg):

        self.logger = logging.getLogger(__name__)
        self.cfg = cfg

    '''
        Common API methods
    '''    

    def get_session(self):

        if os.path.exists(self.cfg.get('plex-trakt-scrobbler', 'session')):
            sessfp = open(self.cfg.get('plex-trakt-scrobbler', 'session'), 'r')
            session = sessfp.read().strip()
            sessfp.close()
        return session

    def _do_trakt_post(self, url, data):

        f = urllib2.Request(url)
        f.add_header('User-Agent', self.USER_AGENT)
        try:
            res = urllib2.urlopen(f, data)
            return json.load(res)
        except urllib2.URLError, e:
            self.logger.error('Unable to submit post data {url} - {error}'.format(
                url=url, error=e))
            raise


    def _get_auth_infos(self):
        args = {
            'client_id': self.CLIENT_ID
        }

        url = urlparse.urlunparse(('https',
                                  'api-v2launch.trakt.tv',
                                  '/oauth/device/code', '', '', ''))

        res = self._do_trakt_post(url, urllib.urlencode(args))

        return res


    def _get_access_token(self, code):
        args = {
            'client_id': self.CLIENT_ID,
            'client_secret': self.CLIENT_SECRET,
            'code': code,
        }
        url = urlparse.urlunparse(('https',
                                  'api-v2launch.trakt.tv',
                                  '/oauth/device/token', '', '', ''))
        res = self._do_trakt_post(url, urllib.urlencode(args))

        return res


    def trakt_auth(self):

        print '== Requesting trakt.tv auth =='

        auth_infos = self._get_auth_infos()
        accepted = 'n'

        print '\nPlease do the following to authorize the scrobbler:\n\n1/ Connect on {auth_url}\n2/ Enter the code: {code}'.format(
                auth_url=auth_infos['verification_url'], code=auth_infos['user_code'])
        while accepted.lower() == 'n':
            print
            accepted = raw_input('Have you authorized me? [y/N] :')

        try:
            access_token_infos = self._get_access_token(auth_infos['device_code'])
        except urllib2.HTTPError, e:
            self.logger.error('Unable to send authorization request {error}'.format(error=e))
            return False

        if not access_token_infos['refresh_token']:
            print access_token_infos['message']
            return


        token = access_token_infos['access_token']

        fp = open(self.cfg.get('plex-trakt-scrobbler', 'session'), 'w')
        fp.write(token)
        fp.close()
        self.logger.info('Trak TV authorization successful.')


    def _do_trakt_auth_post(self, url, data):
        
        try:
            session = self.get_session()

            headers = {
              'Content-Type': 'application/json',
              'Authorization': 'Bearer ' + session,
              'trakt-api-version': '2',
              'trakt-api-key': self.CLIENT_ID
            }

            # timeout in seconds
            timeout = 5
            socket.setdefaulttimeout(timeout)

            request = urllib2.Request(url, data, headers)
            response = urllib2.urlopen(request).read()
            
            self.logger.info('Response: {0}'.format(response))
            return response
        except urllib2.HTTPError as e:
            self.logger.error('Unable to submit post data {url} - {error}'.format(url=url, error=e.reason))
            raise


    def _do_trakt_auth_get(self, url):
        
        return self._do_trakt_auth_post(url, None)

    '''
        Trakt TV API methods
    '''

    def get_media(self, media_id, source):

        self.logger.info('Getting Media information with {source} id: {media_id} from trak.tv.'
            .format(source=source, media_id=media_id))

        url = urlparse.urlunparse(('https','api-v2launch.trakt.tv', '/search', '', '', ''))
        url += '?id_type={source}&id={media_id}'.format(source=source, media_id=media_id)

        try:
            return self._do_trakt_auth_get(url)
        except:
            return None


    def get_movie(self, imdb_id):

        return self.get_media(imdb_id, 'imdb')


    def get_show(self, tvdb_id):

        return self.get_media(tvdb_id, 'tvdb')


    def scrobble_show(self, show_name, season_number, episode_number, progress, scrobble_type):

        self.logger.info('Scrobbling ({scrobble_type}) {show_name} - S{season_number}E{episode_number} - {progress} to trak.tv.'
            .format(show_name=show_name, scrobble_type=scrobble_type, season_number=season_number.zfill(2), episode_number=episode_number.zfill(2), progress=progress))

        data = {}
        data['show'] = {}
        data['show']['title'] = show_name
        data['episode'] = {}
        data['episode']['season'] = int(season_number)
        data['episode']['number'] = int(episode_number)
        data['progress'] = int(progress)
        data['app_version'] = '1.0'
        data['app_date'] = '2014-09-22'
        json_data = json.dumps(data)

        url = urlparse.urlunparse(('https','api-v2launch.trakt.tv', '/scrobble/' + scrobble_type, '', '', ''))

        try:
            self._do_trakt_auth_post(url, json_data)
        except:
            return False

        return True
