'''
data aggregation tools for report purposes
'''

import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

def aggregation_factory(level=0):
    '''chain defaultdicts to create an aggregate for data'''
    if level == 0:
        return []
    return defaultdict(lambda: aggregation_factory(level=level - 1))

def nested(data, *field_names):
    '''
    apply aggregation to data based on field names provided
        nested([item, item, ...], field_a, field_b) ->
            {
                item[field_a]: {                            # item[field_a] == value_a_1
                        item[field_b]: [item, item, ...],   # item[field_b] == value_b_1
                        item[field_b]: [item, item, ...],   # item[field_b] == value_b_2
                        ...
                },
                item[field_a]: {                            # item[field_a] == value_a_2
                        item[field_b]: [item, item, ...],   # item[field_b] == value_b_1
                        ...
                },
                ...
            }
    '''
    aggregate = aggregation_factory(len(field_names))
    for item in data:
        ptr = aggregate
        for field in field_names:
            ptr = ptr[item[field]]
        ptr.append(item)
    return aggregate

def flat(data, *field_names):
    '''
    a flat data aggregator
        flat([item, item, ...], field_a, field_b) ->
            {
                item[field_a], item[field_b]: [item, item, ...],    # item[field_a] == value_a_1, item[field_b] == value_b_1
                item[field_a], item[field_b]: [item, item, ...],    # item[field_a] == value_a_1, item[field_b] == value_b_2
                item[field_a], item[field_b]: [item, item, ...],    # item[field_a] == value_a_1, item[field_b] == value_b_3
                ...
                item[field_a], item[field_b]: [item, item, ...],    # item[field_a] == value_a_2, item[field_b] == value_b_1
                item[field_a], item[field_b]: [item, item, ...],    # item[field_a] == value_a_2, item[field_b] == value_b_2
                ...
            }
    use to aggregate a list of dictionaries by selected key values into a dictionary addressed by tuples of values
    '''
    ret = defaultdict(lambda: [])
    for item in data:
        ret[tuple([item.get(field_name) for field_name in field_names])].append(item)
    return ret
