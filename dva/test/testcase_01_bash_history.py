""" This module contains testcase_01_bash_history test """
from testcase import Testcase
from dva.work.stage import OLD_BASH_HISTORY_FILE as HISTFILE, SSH_USERS
from os import path


class testcase_01_bash_history(Testcase):
    """
    Ensure /root/.bash_history file is empty
    """
    stages = ['stage1']
    tags = ['default']

    # pylint: disable=W0613
    def test(self, connection, params):
        """ Perform test """
        # try all possible cloud users
        for user in SSH_USERS:
            # 'expand' user
            user_histfile = '~' + user + path.sep + path.basename(HISTFILE)
            self.ping_pong(connection, '[ ! -f %s ] && echo 0 || cat %s | wc -l' % (user_histfile, user_histfile), '\r\n0\r\n')

        return self.log
