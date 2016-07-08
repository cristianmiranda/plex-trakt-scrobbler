#!/usr/bin/env python

import ConfigParser
import logging
import os
import platform
import sys
import threading
import time
from optparse import OptionParser

from helper.trakt import Trakt
from monitor import monitor_log


def platform_log_directory():
    """ Retrieves the default platform specific default log location.
        This is called if the user does not specify a log location in
        the configuration file.
    """

    log_defaults = {
        'Darwin': os.path.expanduser('~/Library/Logs/Plex Media Server.log'),
        'Linux': '/var/lib/plexmediaserver/Library/Application Support/Plex Media Server/Logs/Plex Media Server.log',
        'Windows': os.path.join(os.environ.get('LOCALAPPDATA', 'c:'), 'Plex Media Server/Logs/Plex Media Server.log'),
        'FreeBSD': '/usr/local/plexdata/Plex Media Server/Logs/Plex Media Server.log',
    }

    return log_defaults[platform.system()]


def main(config):
    """ The main thread loop

    Args:
        config (ConfigParser obj) : user specific configuration params
    """

    logger.info('Starting log monitor thread...')
    log_watch = threading.Thread(target=monitor_log, args=(config,))
    log_watch.start()

    # main thread ended/crashed. exit.
    log_watch.join()
    sys.exit(1)


if __name__ == '__main__':

    p = OptionParser()
    p.add_option('-c', '--config', action='store', dest='config_file', help='The location to the configuration file.')
    p.add_option('-p', '--precheck', action='store_true', dest='precheck', default=False,
                 help='Run a pre-check to ensure a correctly configured system.')
    p.add_option('-a', '--authenticate', action='store_true', dest='authenticate', default=False,
                 help='Generate a new TVShow Time session key.')
    p.set_defaults(config_file=os.path.expanduser('~/.config/plex-trakt-scrobbler/plex_trakt_scrobbler.conf'))

    (options, args) = p.parse_args()

    if not os.path.exists(options.config_file):
        print 'Exiting, unable to locate config file {0}. use -c to specify config target'.format(
            options.config_file)
        sys.exit(1)

    # apply defaults to *required* configuration values.
    config = ConfigParser.ConfigParser(defaults={
        'config file location': options.config_file,
        'session': os.path.expanduser('~/.config/plex-trakt-scrobbler/session_key'),
        'mediaserver_url': 'http://localhost:32400',
        'mediaserver_log_location': platform_log_directory(),
        'log_file': '/tmp/plex_trakt_scrobbler.log'
    })
    config.read(options.config_file)

    FORMAT = '%(asctime)-15s [%(process)d] [%(name)s %(funcName)s] [%(levelname)s] %(message)s'
    logging.basicConfig(filename=config.get('plex-trakt-scrobbler',
                                            'log_file'), format=FORMAT, level=logging.DEBUG)
    logger = logging.getLogger('main')

    # dump our configuration values to the logfile
    for key in config.items('plex-trakt-scrobbler'):
        logger.debug('config : {0} -> {1}'.format(key[0], key[1]))

    # if a valid session object does not exist, prompt user
    # to authenticate.
    if (not os.path.exists(config.get('plex-trakt-scrobbler', 'session')) or
            options.authenticate):
        logger.info('Prompting to authenticate to Trak TV.')
        trakt = Trakt(config)
        trakt.trakt_auth()
        print 'Please relaunch plex-trakt-scrobbler service.'
        logger.warn('Exiting application.')
        sys.exit(0)

    logger.debug('using trakt.tv session key={key} , st_mtime={mtime}'.format(
        key=config.get('plex-trakt-scrobbler', 'session'),
        mtime=time.ctime(os.path.getmtime(config.get('plex-trakt-scrobbler', 'session')))))

    main(config)
