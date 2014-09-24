""" This module contains testcase_37_sshd_bug923996 test """
from testcase import Testcase
from distutils.version import LooseVersion as Version


class testcase_37_sshd_bug923996(Testcase):
    """
    Perform test against bug #923996: multiple PermitRootLogin=... in /etc/ssh/sshd_config
    """
    stages = ['stage2']
    tags = ['default']
    applicable = {
        'product': '(?i)RHEL|BETA',
        'version': lambda ver: ver >= Version('5.5') and ver < Version('5.10') or \
                            ver >= Version('6.4') and ver < Version('7.0')
    }

    def test(self, connection, params):
        """ Perform test """

        if params['version'].startswith('5.'):
            self.get_return_value(connection, '[ `grep ^PermitRootLogin /etc/ssh/sshd_config | wc -l` -lt 2 ]')
        if params['version'].startswith('6.'):
            self.get_return_value(connection, '[ `grep ^PermitRootLogin /etc/ssh/sshd_config | wc -l` -eq 0 ]')
        return self.log
