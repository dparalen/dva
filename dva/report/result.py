""" Result parsing functions """
import textwrap
import aggregate
from ..work.common import RESULT_PASSED, RESULT_FAILED, RESULT_ERROR, RESULT_SKIP

COMMON_COMMAND_KEYS_ORDERED=('command', 'match', 'result', 'value', 'actual', 'expected', 'comment')

def command_repr(command):
    '''repr a single command as list of lines'''
    ret = []
    format_value = lambda key, value: textwrap.wrap(('%s: ' % key) + str(value), initial_indent='  ',
                        subsequent_indent='  ', break_on_hyphens=False,  break_long_words=True, width=70)
    ret.append('-')
    for key in COMMON_COMMAND_KEYS_ORDERED:
        if key not in command:
            continue
        ret.extend(format_value(key, command[key]))
    for key in set(command) - set(COMMON_COMMAND_KEYS_ORDERED):
        ret.extend(format_value(key, command[key]))
    return ret


def get_test_result(test_data, verbose=False):
    '''get formated test result'''
    ret = test_data['result']
    log = ['%s:%s: %s' % (test_data['stage'], test_data['name'], test_data['result'])]
    if test_data['result'] != RESULT_PASSED or verbose:
         for command in test_data['log']:
            log.extend(command_repr(command))
    return ret, log


def get_stage_result(stage_data, verbose=False):
    '''get formated stage result'''
    ret = stage_data['stage_result']
    log = []
    if ret != RESULT_PASSED or verbose:
        log = ['-']
        txt = '%s: %s\n%s' % (stage_data['stage_name'], stage_data['stage_result'], stage_data['stage_exception'])
        log.extend(textwrap.wrap(txt, break_on_hyphens=False, break_long_words=True, width=70, initial_indent='  ',
                                    subsequent_indent='  '))
    return ret, log


def get_hwp_result(data, verbose=False):
    '''get overal hwp result'''
    ret = RESULT_PASSED
    log = []
    for res in data:
        if 'test' in res:
            # test case result
            sub_result, sub_log = get_test_result(res['test'], verbose)
        else:
            # stage result
            sub_result, sub_log = get_stage_result(res, verbose)
        if sub_result in [RESULT_ERROR, RESULT_FAILED, RESULT_SKIP] and ret == RESULT_PASSED:
            ret = sub_result
        log.extend(sub_log)
    return ret, log

def get_ami_result(data, verbose=False):
    '''get overal ami result'''
    ret = RESULT_PASSED
    log = []
    for hwp in data:
        hwp_index = len(log)
        sub_result, sub_log = get_hwp_result(data[hwp], verbose)
        if sub_result not in [RESULT_PASSED, RESULT_SKIP] and ret == RESULT_PASSED:
           ret = sub_result
        header = '%s: %s' % (hwp, sub_result)
        log.insert(hwp_index, '-' * len(header))
        log.insert(hwp_index, header)
        log.insert(hwp_index, '')
        log.extend(sub_log)
    return ret, log

def get_overall_result(data, verbose=False):
    """
    Get human-readable representation of the result; partitioned by ami
    returns a tuple of an overal result and list of tuples overal_result, [(ami_resutl, ami_log), ...]
    """
    agg_data = aggregate.nested(data, 'region', 'arch', 'itype', 'ami', 'cloudhwname')
    ret = RESULT_PASSED
    log = []
    for region in agg_data:
        for arch in agg_data[region]:
            for itype in agg_data[region][arch]:
                for ami in agg_data[region][arch][itype]:
                    sub_result, sub_log = get_ami_result(agg_data[region][arch][itype][ami], verbose)
                    if sub_result != RESULT_PASSED and ret == RESULT_PASSED:
                        ret = sub_result
                    ami_header = '%s %s %s %s: %s' % (region, arch, itype, ami, ret)
                    sub_log.insert(0, '-' * len(ami_header))
                    sub_log.insert(0, ami_header)
                    log.append((sub_result, sub_log))
    return ret, log
