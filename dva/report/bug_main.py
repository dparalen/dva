'''
the bugzilla report function module
'''
import sys
import time
import logging
import bugzilla
import tempfile
import aggregate
from ..tools.retrying import retrying, EAgain
from ..work.data import load_yaml, save_result
from ..work.common import RESULT_PASSED, RESULT_SKIP
from result import get_hwp_result
from gevent.pool import Pool
from gevent.coros import RLock
import yaml
try:
    from yaml import CDumper as Dumper
except ImportError:
    from yaml import Dumper

logger = logging.getLogger(__name__)
DEFAULT_URL='https://bugzilla.redhat.com/xmlrpc.cgi'
DEFAULT_COMPONENT='images'
DEFAULT_PRODUCT='Cloud Image Validation'
MAXTRIES=40
SLEEP=3


def bugzilla_credentials(configfile):
    '''get bugzilla credentials from a config file'''
    config = load_yaml(configfile)
    return config['bugzilla']['user'], config['bugzilla']['password']


@retrying(maxtries=MAXTRIES, sleep=SLEEP)
def connect(url, user, password):
    '''connect to bugzilla, return the bugzilla connection'''
    ret = bugzilla.RHBugzilla(url=url, user=user, password=password)
    if not ret:
        raise RuntimeError("Couldn't connect to bugzilla: %s %s %s" % (url, username, password))
    logger.debug('connected to bugzilla: %s %s %s %s', url, user, password, ret)
    return ret

@retrying(maxtries=MAXTRIES, sleep=SLEEP)
def create_bug(connection, summary, version, arch, component=DEFAULT_COMPONENT, product=DEFAULT_PRODUCT,
    op_sys='Linux', keywords=['TestOnly']):
    '''create particular bug'''
    return connection.createbug(product=product, component=component, version='RHEL' + str(version),
                rep_platform=arch, summary=summary, op_sys=op_sys, keywords=keywords)

@retrying(maxtries=MAXTRIES, sleep=SLEEP, final_exception=AssertionError)
def assert_bug(connection, bug):
    '''assert a bug exists'''
    try:
        return connection.getbug(bug.bug_id)
    except bugzilla.Fault as err:
        raise EAgain(err)

@retrying(maxtries=MAXTRIES, sleep=SLEEP)
def create_bug_log_attachment(connection, bug, ami, data):
    '''create bug attachment from data'''
    with tempfile.NamedTemporaryFile() as fd:
        logger.debug('%s got attachment tmpfile: %s', ami, fd.name)
        fd.write(yaml.dump(data, Dumper=Dumper))
        fd.seek(0)
        assert_bug(connection, bug)
        logger.debug('uploading %s log attachment', ami)
        attach_name = ami + '-log.yaml'
        res = connection.attachfile(bug.bug_id, fd, attach_name, filename=attach_name, contenttype='text/yaml', ispatch=False)
        logger.debug('uploading %s log attachmet done: %s', ami, res)

@retrying(maxtries=MAXTRIES, sleep=SLEEP)
def comment_bug(connection, bug, comment):
    res = assert_bug(connection, bug).addcomment(comment)
    logger.debug('bz %s added comment %s: %s', bug.bug_id, comment, res)


def process_ami_record(ami, version, arch, region, itype, user, password, ami_data,
        url=DEFAULT_URL, component=DEFAULT_COMPONENT, product=DEFAULT_PRODUCT, verbose=False):
    '''process one ami record creating bug with comment per hwp'''
    connection = connect(url, user, password)
    summary = '%s %s %s %s %s' % (ami, version, arch, itype, region)
    bug = create_bug(connection, summary, version, arch, component, product)
    create_bug_log_attachment(connection, bug, ami, ami_data)
    ami_result = RESULT_PASSED
    for hwp in ami_data:
        sub_result, sub_log = get_hwp_result(ami_data[hwp], verbose)
        if sub_result not in [RESULT_PASSED, RESULT_SKIP] and ami_result == RESULT_PASSED:
            ami_result = sub_result
        bug.addcomment('# %s: %s\n%s' % (hwp, sub_result, '\n'.join(sub_log)))
    bug.setstatus(ami_result == RESULT_PASSED and 'VERIFIED' or 'ON_QA')
    return bug.bug_id, ami, ami_result


def main(config, istream, ostream, user=None, password=None, url=DEFAULT_URL,
            component=DEFAULT_COMPONENT, product=DEFAULT_PRODUCT, verbose=False, pool_size=128):
    user, password = bugzilla_credentials(config)
    logger.debug('got credentials: %s, %s', user, password)
    statuses = []
    data = load_yaml(istream)
    agg_data = aggregate.nested(data, 'region', 'version', 'arch', 'itype', 'ami', 'cloudhwname')
    for region in agg_data:
        logger.debug(region)
        for version in agg_data[region]:
            logger.debug(version)
            for arch in agg_data[region][version]:
                logger.debug(arch)
                for itype in agg_data[region][version][arch]:
                    logger.debug(itype)
                    for ami in agg_data[region][version][arch][itype]:
                        logger.debug(ami)
                        statuses.append((ami, version, arch, region, itype, user, password,
                             agg_data[region][version][arch][itype][ami], url,
                             component, product))
    pool = Pool(size=pool_size)
    statuses = pool.map(lambda args: process_ami_record(*args), statuses)
    for bug, ami, status in statuses:
        save_result(ostream, dict(bug=bug, id=ami, status=status))
    return all([status == RESULT_PASSED for _, status, _ in statuses]) and 0 or 1

