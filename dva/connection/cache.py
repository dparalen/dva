'''
cache and tools
'''
from gevent import getcurrent, socket

import sys
import logging
import traceback
import paramiko
from ..tools.retrying import retrying, EAgain
from .. import cloud, work
from stitches import Connection, Expect, ExpectFailed
from stitches.connection import StitchesConnectionException
from weakref import WeakValueDictionary


CONNECTION_ATTEMPTS = 120
CONNECTION_ATTEMPTS_RETRY_AFTER = 1
CONNECTION_CACHE = WeakValueDictionary()

logger = logging.getLogger(__name__)

class ConnectionCacheError(Exception):
    '''bad things happen in connection cache'''

def connection_cache_key(params):
    '''params to connection cache key tuple: (None, host, user, key)'''
    try:
        return id(getcurrent()), params['hostname'], params['ssh']['user'], params['ssh']['keyfile']
    except KeyError as err:
        # some key is missing in params
        raise ConnectionCacheError('params missing key: %s' % err)

def drop_connection(params):
    """ Close&remove connection """
    key = connection_cache_key(params)
    try:
        CONNECTION_CACHE.pop(key).disconnect()
        logger.debug('dropped: %s', key)
    except KeyError as err:
        pass

def assert_connection(connection):
    '''assert a connection is alive; wel... ;) at a point in time'''
    try:
        logger.debug('asserting connection: %s', connection)
        Expect.ping_pong(connection, 'uname', 'Linux')
        logger.debug('asserting connection: %s passed', connection)
    except (IOError, socket.error, socket.timeout, StitchesConnectionException, ExpectFailed, \
            paramiko.ssh_exception.AuthenticationException, paramiko.ssh_exception.SSHException) as err:
        logger.debug('asserting %s got: %s(%s): %s', connection, type(err), err, traceback.format_exc())
        raise EAgain(err)

@retrying(maxtries=CONNECTION_ATTEMPTS, sleep=CONNECTION_ATTEMPTS_RETRY_AFTER, loglevel=logging.DEBUG,
            final_exception=ConnectionCacheError)
def get_connection(params):
    '''Get connection connection based on params. Retrying.'''
    # maybe the connection is cached...
    key = connection_cache_key(params)
    try:
        connection = CONNECTION_CACHE[key]
        logger.debug('cache hit: %s', key)
    except KeyError as err:
        logger.debug('cache miss: %s', key)
        _, host, user, ssh_key = key
        CONNECTION_CACHE[key] = connection =  Connection(host, user, ssh_key)
        logger.debug('got new connection: %s', connection)

    try:
        # make sure the connection is alive
        assert_connection(connection)
        logger.debug('got alive connection: %s', connection)
    except EAgain as err:
        # something went wrong --- drop and keep retrying
        logger.debug('got %s asserting %s --- dropping connection', err, connection)
        drop_connection(params)
        work.params.reload(params)
        raise err
    # got connection --- return
    return connection
