import os
import re
import random
import logging
from collections import defaultdict
from ..tools.registry import TEST_STAGES, TEST_CLASSES
from ..tools.namespace import load_ns, dump_ns
from tags_filter import factory as applicability_factory
from functools import wraps

from yaml import load as yload
from yaml import dump_all as ysafe_dump_all
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper


logger = logging.getLogger(__name__)
HWP_PATHS = ['./hwp/', '/usr/share/dva/hwp']
CONFIG_FILES = ['dva.yaml', '~/.dva.yaml', '/etc/dva.yaml']

DEFAULT_FIELDS = {
    'cloud': 'ec2',
    'enabled': True,
    'bmap': {},
    'userdata': ''
}

EPHEMERAL_FIELDS = ['credentials', 'global_setup_script', 'instance', 'ssh', 'test_stages', 'user_data',
        'bmap', 'enabled', 'userdata', 'test_whitelist', 'test_blacklist', 'stage_whitelist', 'stage_blacklist',
        'tags_whitelist', 'tags_blacklist']
RE_ALL = re.compile('.*')

class DataError(Exception):
    '''data wasn't OK'''

class ConfigError(Exception):
    '''configuration wasn't OK'''

def load_yaml(filename):
    ''' load yaml file'''
    if isinstance(filename, file):
        return yload(filename, Loader=Loader)

    with open(filename) as datafd:
        data = yload(datafd, Loader=Loader)
    return data

def arch_to_path(arch):
    '''return path to first arch if found in HWP_PATHS; raise otherwise'''
    filename = lambda dirname: os.path.join(dirname, str(arch) + '.yaml')
    arch_files = [filename(dirname) for dirname in HWP_PATHS if os.path.exists(filename(dirname))]
    assert arch_files, 'wrong arch: %s.yaml not found in any of %s' % (arch, HWP_PATHS)
    logger.debug('using hwp(arch) file: %s', arch_files[0])
    return arch_files[0]

def record_cloud_config(record, config_file=None):
    '''put cloud config data into a record; first found config file is used'''
    if config_file is None:
        # no config file given, try locating some in default spots
        config_files = [filename for filename in CONFIG_FILES if os.path.exists(filename)]
        assert config_files, 'could not locate any config file; tried: %s' % CONFIG_FILES
        config_file = config_files[0]
    logger.debug('using cloud config file: %s', config_file)
    # e.g. record['cloud'] == 'ec2' -> config['cloud_access']['ec2']
    try:
        region = record['region']
        cloud = record['cloud']
    except KeyError as err:
        raise DataError('record %r misses %s' % (record, err))
    try:
        config = load_yaml(config_file)['cloud_access'][cloud]
        # provide cloud credentials
        record['credentials'] = {
            'ec2_access_key': config['ec2_access_key'],
            'ec2_secret_key': config['ec2_secret_key']
        }
        # provide ssh config
        ssh_config = config['ssh'][region]
        record['ssh'] = {
            'keypair': ssh_config[0],
            'keyfile': ssh_config[1]
        }
    except KeyError as err:
        raise ConfigError('config %s(:ssh) misses %s' % (config_file, err))
    except IndexError as err:
        raise ConfigError('config %s:ssh.%s misses an item (%s)' % (config_file, region, err))
    except Exception as err:
        raise ConfigError('config %s: %s' % (config_file, err))
    return record


def expand_record_arch(record):
    '''return a list of arch-expanded records'''
    assert type(record) is dict
    try:
        arch_data = load_yaml(arch_to_path(record['arch']))
    except KeyError as err:
        raise DataError('record %r: %s' % (record, err))
    return [dict(record.items() + arch_item.items()) for arch_item in arch_data]

def expand_record_tests(record):
    '''
    expand record with test-case/stage lists:
    - adds record['test_stages'] what is a dictionary of lists of test_names
    - e.g. {'stage1': [test_a, test_b, ...], 'stage2': [test_x, test_y, ...], ...}
    takes care of applicability and black/white-listing
    '''
    assert type(record) is dict
    app_filter = lambda test_class: getattr(test_class, 'applicable', defaultdict(lambda: None))
    not_filter = lambda test_class: getattr(test_class, 'not_applicable', defaultdict(lambda: None))
    tags = lambda test_class: getattr(test_class, 'tags', ['default'])
    record['test_stages'] = \
    { stage: \
        [
            test_name for test_name in sorted(TEST_STAGES[stage]) if \
                applicability_factory(applicable=app_filter(TEST_CLASSES[test_name]), \
                                        not_applicable=not_filter(TEST_CLASSES[test_name]))(record) and \
                any([re.match(pattern, test_name) for pattern in record.get('test_whitelist', ['.*'])]) and \
                not any([re.match(pattern, test_name) for pattern in record.get('test_blacklist', [])]) and \
                any([re.match(pattern, tag) for tag in tags(TEST_CLASSES[test_name]) \
                    for pattern in record.get('tags_whitelist', ['default'])]) and \
                not any([re.match(pattern, tag) for tag in tags(TEST_CLASSES[test_name]) \
                    for pattern in record.get('tags_blacklist', [])])
        ]
        for stage in sorted(TEST_STAGES) if \
            any([re.match(pattern, stage) for pattern in record.get('stage_whitelist', ['.*'])]) and \
            not any([re.match(pattern, stage) for pattern in record.get('stage_blacklist', [])])
    }
    return record

def normalize_record(record):
    '''return a record with normalized fields'''
    assert type(record) is dict
    # make sure all is lowercase and "safe"
    tmp = load_ns(record, leaf_processor=lambda value: type(value) is str and value.lower() or value)
    record = dump_ns(tmp)
    # override any defaults with original record
    # to prevent any missing fields
    return dict(DEFAULT_FIELDS.items() + record.items())

def load(path, config_file=None, augment={}, shuffle=True):
    '''load data and process it; returns list of expanded records
       all **kvs are propagated to the data
    '''
    data = load_yaml(path)
    ret = []
    for record in data:
        record.update(augment)
        ret.extend([expand_record_tests(record) for record in expand_record_arch( \
                        record_cloud_config(normalize_record(record), config_file))])
    # shuffle to avoid single region exhaustion
    if shuffle:
        random.shuffle(ret)
    return ret

def save_result(stream, result):
    '''shortcut for ydump_all(data, stream, Dumper=Dumper)'''
    #result = dump_ns(result, leaf_processor=lambda value: type(value) is unicode and str(value) or value)
    if isinstance(stream, file):
        ysafe_dump_all([[result]], stream, Dumper=Dumper)
    else:
        with open(stream, 'w') as fd:
            ysafe_dump_all([[result]], fd, Dumper=Dumper)



def brief(record):
    '''return a brief info about the record'''
    return '%(region)s %(ami)s %(cloudhwname)s %(product)s %(version)s %(itype)s' % record


def strip_ephemeral(record):
    '''strip ephemeral record fields such as host names, instance details, authentication'''
    ret = record.copy()
    for field_name in EPHEMERAL_FIELDS:
        try:
            del(ret[field_name])
        except KeyError:
            pass
    return ret
