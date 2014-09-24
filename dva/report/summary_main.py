'''
validation summary report function module
'''
import sys
import time
import logging
import bugzilla
import tempfile
import aggregate
from ..tools.retrying import retrying, EAgain
from ..work.data import load_yaml, save_result
from ..work.common import RESULT_PASSED
from result import get_hwp_result
from gevent.pool import Pool
from gevent.coros import RLock
import yaml
try:
    from yaml import CDumper as Dumper
except ImportError:
    from yaml import Dumper

logger = logging.getLogger(__name__)

def print_failed(data, aname, area, whitelist):
    agg_data = aggregate.flat(data, area)
    for name,data in agg_data.items():
        print('%s %s' % (aname, name[0]))
        for test in data:
            if test.has_key('test'):
                if test['test']['result'] != 'passed':
                    if test['test']['name'] not in whitelist:
                        print('   Failed test %s' % test['test']['name'])

def main(config, istream,test_whitelist,compare):
    logger.debug('starting generation from file %s',istream)
    data = load_yaml(istream)
    comparelist = [str(item) for item in compare[0].split(',')]
    whitelist = [str(item) for item in test_whitelist[0].split(',')]
    for area in comparelist:
        if area == 'cloudhwname':
            aname = 'HWNAME:'
            print_failed(data,aname,area,whitelist)
        elif area == 'region':
            aname = 'REGION:'
            print_failed(data,aname,area,whitelist)
        else:
            area = 'ami'
            aname = 'AMI:'
            print_failed(data,aname,area,whitelist)
