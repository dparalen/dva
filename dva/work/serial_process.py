'''
basic serial test processor
'''
import time
import logging
import traceback
from stage import create_instance, attempt_ssh, allow_root_login, global_setup_script, terminate_instance
from test import execute_stages, TEST_WORKER_POOL_SIZE
from common import RESULT_ERROR
from stage import STAGES, StageError, SkipError


logger = logging.getLogger(__name__)


def process(params, pool_size=TEST_WORKER_POOL_SIZE):
    '''process required acctions'''
    terminate = False
    try:
        params = create_instance(params)
        terminate = True
        yield params
        params = attempt_ssh(params)
        yield params
        params = allow_root_login(params)
        yield params
        params = global_setup_script(params)
        yield params
        for test_result in execute_stages(params, pool_size=pool_size):
            yield test_result
    except SkipError as err:
        logger.debug('encountered skip error: %s', err)
        yield params
    except StageError as err:
        logger.debug('encountered stage error: %s', err)
        yield params
    except Exception as err:
        # unhandled error
        logger.error('unhandled exception: %s(%s)', type(err), err)
        params['stage_exception'] = traceback.format_exc()
        params['stage_result'] = RESULT_ERROR
        yield params
    finally:
        if terminate:
            yield terminate_instance(params)

def required_actions_count(params):
    total = 0
    for item in params:
        total += len(STAGES)
        for test_stage in item['test_stages']:
            for test_name in item['test_stages'][test_stage]:
                total += 1
    return total

def print_progress_info(actual, total):
    '''print progress info actual/total'''
    print '# %s %2.2f%% (%s/%s)' % (time.ctime(), float(actual * 100)/total, actual, total)


