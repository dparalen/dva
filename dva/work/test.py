'''
the test execution module
'''


import sys
import time
import logging
import traceback
from stitches import Expect
from ..tools.registry import TEST_CLASSES, TEST_STAGES
from ..tools.logged import logged
from ..connection.cache import get_connection, assert_connection, connection_cache_key, drop_connection, ConnectionCacheError
from data import brief
from params import when_enabled
from params import reload  as params_reload
from common import RESULT_ERROR, RESULT_PASSED, RESULT_FAILED
from ..tools.retrying import retrying
from ..connection.contextmanager import connection as connection_ctx
from ..connection.contextmanager import alive_connection

TEST_WORKER_POOL_SIZE = 10 # the default SSH MaxSessions value


logger = logging.getLogger(__name__)

class TestingError(Exception):
    '''Some testing issue appeared'''

@when_enabled
def test_execute(params):
    """
    Testing stage: perform all tests required in params
    @param params: testing parameters
    @type params: dict
    @return: list of test results
    """
    assert 'test' in params, 'test field missing in %s' % brief(params)
    assert 'name' in params['test'], 'test name field missing in %s' % brief(params)
    assert 'stage' in params['test'], 'test stage field missing in %s' % brief(params)
    test_name = params['test']['name']
    test_stage = params['test']['stage']
    params['test']['exception'] = None
    params['test']['log'] = []
    params['test']['result'] = RESULT_PASSED
    hostname = params['hostname']

    logger.debug('trying %s %s %s', hostname, test_stage, test_name)
    try:
        test_cls = TEST_CLASSES[test_name]
        stage = TEST_STAGES[test_stage]
        assert test_name in stage, 'could not locate test %s in stage %s' % (test_name, test_stage)
    except KeyError as err:
        params['test_result'] = 'error: missing test/stage: %s/%s' % (test_name, test_stage)
        raise TestingError('missing test: %' % test_name)

    # asserts connection; tries reconnecting
    con = get_connection(params)
    # perform the testing
    try:
        test_obj = test_cls()
        test_obj.test(con, params)
        logger.debug('%s %s %s succeeded', hostname, test_stage, test_name)
    except AssertionError as err:
        # not caught in the test case but means the test failed
        params['test']['result'] = RESULT_FAILED
        params['test']['exception'] = traceback.format_exc()
    else:
        # no assertion errors detected --- check all cmd logs
        test_cmd_results = [cmd['result'] for cmd in test_obj.log if 'result' in cmd]
        test_result = RESULT_FAILED in test_cmd_results and RESULT_FAILED or RESULT_PASSED
        test_result = RESULT_ERROR in test_cmd_results and RESULT_ERROR or test_result
        params['test']['result'] = test_result
    finally:
        params['test']['log'] = test_obj.log
    return params

@when_enabled
def reboot_instance(params):
    '''call a reboot'''
    with alive_connection(params) as connection:
        Expect.expect_retval(connection, 'nohup sleep 1s && nohup reboot &')
    time.sleep(10)

@when_enabled
@retrying(maxtries=60, sleep=3, loglevel=logging.DEBUG)
def wait_boot_instance(params):
    '''wait till the instance boots'''
    params_reload(params)
    _, host, user, ssh_key = connection_cache_key(params)
    with connection_ctx(host, user, ssh_key) as connection:
        assert_connection(connection)

def process_dependencies(stage_name, test_names):
    '''process process dependencies for particular stage name; yields etages of dep tree'''
    from ..tools.dependency import Graph, Vertex, bfs
    # build the graph
    root = Vertex(value='__root__')
    graph = Graph(vertices=set([root]))
    for test_name in test_names:
        logger.debug('processing testcase %s dependencies', test_name)
        test_vertex = Vertex(value=test_name)
        dep_names = getattr(TEST_CLASSES[test_name], 'after',  [])
        # in case no dependencies were specified, the test depends on the root vertice
        deps = [Vertex(dep_name) for dep_name in dep_names if dep_name in test_names] or [root]
        for dep in deps:
            logger.debug('adding dependency %s, %s', dep, test_vertex)
            graph.add_edge(dep, test_vertex)

    # evaluate dependencies; skip the root-only etage
    for vertex_etage in bfs(graph, root):
        test_names = [vertex.value for vertex in vertex_etage if vertex.value != '__root__']
        yield test_names



def execute_tests(original_params, stage_name, pool_size=TEST_WORKER_POOL_SIZE):
    '''perform all tests'''
    from gevent.pool import Pool
    pool = Pool(size=pool_size)
    for test_etage in process_dependencies(stage_name, original_params['test_stages'][stage_name]):
        for result in pool.map(test_execute, [dict(test=dict(name=test_name, stage=stage_name), **original_params) \
                for test_name in test_etage]):
            yield result

def execute_stages(params, pool_size=TEST_WORKER_POOL_SIZE):
    '''perform all stages'''
    params['stage_name'] = 'execute_tests'
    stages = sorted(params['test_stages'])
    # reboots inbetween stages
    for stage_name in stages[:-1]:
        if not params['test_stages'][stage_name]:
            logger.debug('skipping empty test stage: %s', stage_name)
            continue # avoid rebooting on empty stages
        for result in execute_tests(params, stage_name, pool_size=pool_size):
            yield result
        reboot_instance(params)
        wait_boot_instance(params)
    # no reboot at last stage exit
    for result in execute_tests(params, stages[-1]):
        yield result
