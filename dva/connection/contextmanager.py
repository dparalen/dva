'''
connection ctx manager module
'''

import stitches
import contextlib
import logging
from ..tools.retrying import retrying, EAgain
from cache import CONNECTION_ATTEMPTS, CONNECTION_ATTEMPTS_RETRY_AFTER, assert_connection, connection_cache_key

@contextlib.contextmanager
def connection(host, user, key):
    '''ctx manager for connections'''
    con = stitches.Connection(host, user, key)
    try:
        yield con
    finally:
        con.disconnect()
        del(con)


@contextlib.contextmanager
@retrying(maxtries=CONNECTION_ATTEMPTS, sleep=CONNECTION_ATTEMPTS_RETRY_AFTER, loglevel=logging.DEBUG)
def alive_connection(params):
    '''a context manager yielding an asserted/alive connection'''
    _, host, user, ssh_key = connection_cache_key(params)
    with connection(host, user, ssh_key) as con:
        assert_connection(con)
        yield con
