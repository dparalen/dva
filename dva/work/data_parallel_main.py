'''
basic data-parallel main function module
'''

from gevent.coros import RLock
from gevent.pool import Pool

import logging
from data import load, save_result, strip_ephemeral
from serial_process import process, required_actions_count, print_progress_info
from serial_main import process, required_actions_count, print_progress_info
logger = logging.getLogger(__name__)

PROCESSED=0
TOTAL=0

REPORT_LOCK = RLock()


def target(ostream, params, parallel_tests):
    global PROCESSED, REPORT_LOCK, TOTAL
    for result in process(params, pool_size=parallel_tests):
        with REPORT_LOCK:
            PROCESSED += 1
            print_progress_info(PROCESSED, TOTAL)
            save_result(ostream, strip_ephemeral(result))



def main(conf, istream, ostream, test_whitelist, test_blacklist, stage_whitelist, stage_blacklist,
            tags_whitelist, tags_blacklist, no_action, parallel_instances, parallel_tests):
    ''' main parallel-data worker function'''
    global TOTAL
    params = dict(test_whitelist=test_whitelist, test_blacklist=test_blacklist,
                    stage_whitelist=stage_whitelist, stage_blacklist=stage_blacklist,
                    tags_whitelist=tags_whitelist, tags_blacklist=tags_blacklist,
                   enabled=not no_action)
    params = load(istream, config_file=conf, augment=params)
    TOTAL = required_actions_count(params)
    print_progress_info(PROCESSED, TOTAL)
    pool = Pool(size=parallel_instances)
    pool.map(lambda item: target(ostream, item, parallel_tests), params)

