'''
work stages
'''

import logging
import time
import os
import traceback
from functools import wraps
from stitches import Expect, ExpectFailed
from stitches.connection import StitchesConnectionException
from .. import cloud
from ..tools.retrying import retrying, EAgain
from ..connection.cache import get_connection, assert_connection, connection_cache_key, drop_connection, ConnectionCacheError
from ..connection.contextmanager import connection as connection_ctx
from data import brief
from common import RESULT_ERROR, RESULT_PASSED, RESULT_SKIP, CLOUD_DRIVER_MAXWAIT
from params import when_enabled

logger = logging.getLogger(__name__)

CLOUD_CREATE_WAIT=10
CREATE_ATTEMPTS=360
SETUP_ATTEMPTS = 30
SETUP_SETTLEWAIT = 30
SSH_USERS = ['root', 'ec2-user', 'fedora']
DEFAULT_GLOBAL_SETUP_SCRIPT_TIMEOUT = 120
OLD_BASH_HISTORY_FILE = '~/DVA_OLD_BASH_HISTORY'

STAGES={}

class StageError(RuntimeError):
    '''a stage failed'''

class InstantiationError(StageError):
    '''Create instance failed'''

class SetUpError(StageError):
    '''Setting-up instance failed'''

class SkipError(StageError):
    '''skip particular data entry'''


def stage(fn):
    '''stage handling decorator; saves stage name and status'''
    @wraps(fn)
    def wrapper(params):
        params['stage_name'] = fn.__name__
        params['stage_exception'] = None
        try:
            ret = fn(params)
            params['stage_result'] = RESULT_PASSED
        except SkipError as err:
            # e.g. hw not supported in region
            params['stage_exception'] = traceback.format_exc()
            params['stage_result'] = RESULT_SKIP
            raise SkipError('%s: %s' % (fn.__name__, err))
        except StageError as err:
            params['stage_exception'] = traceback.format_exc()
            params['stage_result'] = RESULT_ERROR
            raise StageError('%s: %s' % (fn.__name__, params['stage_exception']))
        # propagate
        params.update(ret)
        return params
    STAGES[fn.__name__] = (wrapper, fn)
    return wrapper


@stage
@when_enabled
@retrying(maxtries=CREATE_ATTEMPTS, sleep=CLOUD_CREATE_WAIT, loglevel=logging.DEBUG, final_exception=InstantiationError)
def create_instance(params):
    """
    Create stage of testing
    @param params: testing parameters
    @type params:  dict
    """
    driver = cloud.get_driver(params['cloud'], logger, CLOUD_DRIVER_MAXWAIT)
    try:
        driver.create(params)
    except cloud.base.TemporaryCloudException as err:
        logger.debug('Temporary Cloud Exception: %s', err)
        raise EAgain(err)
    except cloud.base.SkipCloudException as err:
        # this instance type can't be created in this region
        logger.debug('Skip Cloud Exception: %s', err)
        raise SkipError(err)
    return params


def save_bash_history(connection):
    '''prevent dva messing with bash history by saving any original history in a separate file'''
    # save old hist, but just once i.e. do not copy history if old hist file already exist
    Expect.ping_pong(connection, '[ -f ~/.bash_history -a ! -f %s ] && cp -f ~/.bash_history %s ; touch %s ; echo "###DONE###"' % \
            (OLD_BASH_HISTORY_FILE, OLD_BASH_HISTORY_FILE, OLD_BASH_HISTORY_FILE), '(?s).*\r\n###DONE###\r\n.*', 10)

@stage
@when_enabled
@retrying(maxtries=SETUP_ATTEMPTS, sleep=10, loglevel=logging.DEBUG, final_exception=SetUpError)
def attempt_ssh(params):
    '''
    waits till ssh is working on the remote host
    @return: the user that was able to logg-in
    '''
    user = None
    hostname = params['hostname']
    ssh_key = params['ssh']['keyfile']
    # try different users; first succesful wins
    for user in SSH_USERS:
        logger.debug('logging-in %s %s %s', hostname, user, ssh_key)
        try:
            with connection_ctx(hostname, user, ssh_key) as con:
                assert_connection(con)
                save_bash_history(con)
        except EAgain as err:
            logger.debug('%s %s %s connection failure: %s --- trying other user', hostname, user, ssh_key, err)
        else:
            # found user --- break
            logger.debug('%s found user: %s', hostname, user)
            break
    else:
        # no user was able to log-in (yet) --- retry
        raise EAgain('not able to connect to %s with any user: %s' % (hostname, SSH_USERS))

    params['ssh']['user'] = user
    return params


@stage
@when_enabled
@retrying(maxtries=3, sleep=3, final_exception=SetUpError)
def allow_root_login(params):
    '''allow root ssh login'''
    _, host, user, ssh_key = connection_cache_key(params)
    if user  == 'root':
        # user root --- nothing to do
        logger.debug('user already root for %s', brief(params))
        return params

    from textwrap import dedent
    command = dedent(r'''
        sudo cp -af /home/%s/.ssh/authorized_keys /root/.ssh/authorized_keys && \
        sudo chown root.root /root/.ssh/authorized_keys && \
        sudo restorecon -Rv /root/.ssh && \
        echo SUCCESS
    ''' % user)

    # Exceptions cause retries, save for ExpectFailed
    with connection_ctx(host, user, ssh_key) as con:
        save_bash_history(con)
        try:
            Expect.ping_pong(con, command, '(?s).*\r\nSUCCESS\r\n.*')
        except ExpectFailed as err:
            # retry
            raise EAgain(err)

    # update user to root
    params['ssh']['user'] = 'root'
    return params


@stage
@when_enabled
def global_setup_script(params):
    """
    Custom Setup stage of testing
    @param params: testing parameters
    @type params:  dict
    """
    hostname = params['hostname']
    script = None
    try:
        script = params['global_setup_script']
        logger.debug('%s %s got global setup script: %s', brief(params), hostname, script)
    except KeyError as err:
        logger.debug('%s no global setup script', brief(params))
    if script is None:
        # nothing to do
        return params

    script = os.path.expandvars(os.path.expanduser(script))
    remote_script = '/tmp/' + basename(script)

    script_timeout = params.get('global_setup_script_timeout', DEFAULT_GLOBAL_SETUP_SCRIPT_TIMEOUT)

    con = get_connection(params)
    logger.debug('%s: got connection', hostname)
    con.sftp.put(script, remote_script)
    logger.debug('%s sftp succeeded %s -> %s', hostname, script, remote_script)
    con.sftp.chmod(remote_script, 0700)
    logger.debug('%s chmod succeeded 0700 %s', hostname, remote_script)
    Expect.ping_pong(con, '%s && echo SUCCESS' % remote_script, '\r\nSUCCESS\r\n', timeout=script_timeout)
    logger.debug('%s set up script finished %s', hostname, remote_script)

    return params



@stage
@when_enabled
@retrying(maxtries=3, sleep=10, final_exception=cloud.PermanentCloudException)
def terminate_instance(params):
    """
    Terminate stage of testing
    @param params: testing parameters
    @type params: dict
    """
    hostname = params['hostname']
    if 'keepalive' in params and params['keepalive']:
        logger.info('will not terminate %s (keepalive requested)', hostname)
        return
    try:
        drop_connection(params)
    except ConnectionCacheError as err:
        logger.debug('not dropping any connection to %s; not in cache', brief(params))
    driver = cloud.get_driver(params['cloud'], logger, CLOUD_DRIVER_MAXWAIT)
    logger.debug('trying to terminate %s', hostname)
    driver.terminate(params)
    logger.info('terminated %s', hostname)
    return params


