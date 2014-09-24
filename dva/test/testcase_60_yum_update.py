""" This module contains testcase_60_yum_update test """
from testcase import Testcase


class testcase_60_yum_update(Testcase):
    """
    Test system update with 'yum update'
    """

    stages = ['stage1']
    tags = ['default', 'content']
    after = ['testcase_55_yum_group_install']
    applicable = {"product": "(?i)RHEL|BETA", "version": "OS (>=5.5, !=6.0)"}

    def test(self, connection, params):
        """ Perform test """

        prod = params['product'].upper()
        ver = params['version']
        if prod in ['RHEL', 'BETA'] and ver.startswith('6.') and params['cloudhwname'] == 't1.micro':
            # Creating swap to workaround mem<1024M issue
            self.ping_pong(connection, 'head -c $((1024*1024*1024)) /dev/zero > /swap && echo SUCCESS', '\r\nSUCCESS\r\n', 150)
            self.get_return_value(connection, 'mkswap /swap', 30)
            self.ping_pong(connection, 'echo \'/swap    swap     swap    defaults     0 0\' >> /etc/fstab && echo SUCCESS', '\r\nSUCCESS\r\n')
            self.get_return_value(connection, 'swapon -a -e', 30)

        # workaround for https://bugzilla.redhat.com/show_bug.cgi?id=912568
        # https://access.redhat.com/site/solutions/175393
        self.get_return_value(connection, 'rpm -q matahari-net && yum -y remove matahari-net ||:', 90)
        if prod in ['RHEL', 'BETA'] and ver.startswith('5.'):
            self.get_return_value(connection, 'yum -y install kernel-xen', 900)
        elif prod == 'FEDORA' and params['arch'] == 'i386':
            self.get_return_value(connection, 'yum -y install kernel-PAE', 900)
        else:
            self.get_return_value(connection, 'yum -y install kernel', 900)
        self.get_return_value(connection, 'yum -y update', 1800)
        if (prod in ['RHEL', 'BETA'] and ver.startswith('5.')) or prod == 'FEDORA':
            # Preparing the latest kernel for stage2 testing
            self.get_return_value(connection, r'sed -i "s,\(default\)=.*$,\1=0," /boot/grub/menu.lst')
        return self.log
