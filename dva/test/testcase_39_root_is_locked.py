""" This module contains testcase_39_root_is_locked test """
from testcase import Testcase


class testcase_39_root_is_locked(Testcase):
    """
    Root account should be locked
    """
    tags = ['default']
    stages = ['stage1']

    # pylint: disable=W0613
    def test(self, connection, params):
        """ Perform test """

        self.get_return_value(connection, 'passwd -S root | grep -q LK')
        return self.log
