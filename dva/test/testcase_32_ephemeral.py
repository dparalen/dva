""" This module contains testcase_32_ephemeral test """
from testcase import Testcase
from os.path import basename


class testcase_32_ephemeral(Testcase):
    """
    It should be possible to use ephemeral device (if we have one)
    Note that in rhel6.5 there is no shift letter in dick device name
    """
    stages = ['stage1']
    tags = ['default']
    after = ['testcase_21_disk_size_format']

    def test(self, connection, params):
        """ Perform test """

        prod = params['product'].upper()
        ver = params['version'].upper()
        ephemerals = []

        if 'bmap' in params:
            ephemerals = [bdev for bdev in params['bmap'] if 'ephemeral_name' in bdev]

        if not ephemerals:
            # are there are some devices to check?
            self.log.append({'result': 'skip',
                             'comment': 'no ephemeral devices in block map'
                             })
            return self.log

        # figure out what fstype to use with focus on mkfs.<fstype> speed
        fstype = None
        for fstype in ['vfat', 'xfs', 'ext3']:
            if self.get_result(connection, 'ls -la /sbin/mkfs.%s 2> /dev/null | wc -l' % fstype, 5) == '1':
                break

        if fstype == 'vfat':
            # so that mkfs.vfat /dev/<device> doesn't complain
            # because of making fs on whole drive instead of a partition
            mkfs_opt = '-I'
        else:
            mkfs_opt = ''

        devices = []
        for bdev in ephemerals:
            name = bdev['name']
            if (prod in ['RHEL', 'BETA']) and (ver.startswith('5.')):
                if name.startswith('/dev/xvd'):
                    # no xvd* for RHEL5
                    continue
            elif (prod in ['RHEL', 'BETA']) and (ver.startswith('6.') and ver != '6.0'):
                if name.startswith('/dev/sd'):
                    name = '/dev/xvd' + name[7:]
                if params['virtualization'] != 'hvm' and ver != '6.5' and len(name) == 9 and ord(name[8]) < ord('w'):
                    # there is a 4-letter shift
                    name = name[:8] + chr(ord(name[8]) + 4)
            else:
                # Fedora and newer RHELs
                if name.startswith('/dev/sd'):
                    name = '/dev/xvd' + name[7:]
            # test: check device presence
            self.get_return_value(connection, 'fdisk -l %s | grep \'^Disk\'' % name, 30)
            if self.get_result(connection, 'grep \'%s \' /proc/mounts  | wc -l' % name, 5) == '0':
                # device is not mounted, doing fs creation
                devices.append(name)

        if not devices:
            return self.log

        mkfs_commands = ['mkfs.%s %s %s' % (fstype, mkfs_opt, name) for name in devices]
        assert self.ping_pong(connection, ' & '.join(mkfs_commands) + ' & echo MKFS', '(?s).*\r\nMKFS.*'), "call mkfs_commands failed"
        assert self.ping_pong(connection, 'wait && echo WAIT', '(?s).*\r\nWAIT.*', 1000), "wait failed?!?!"
        dest_names = ['/tmp/mnt-%s' % basename(name) for name in devices]
        self.get_return_value(connection, 'mkdir -p ' + ' '.join(dest_names))
        mount_commands = ['mount -t %s %s /tmp/mnt-%s' % (fstype, name, basename(name)) for name in devices]
        self.get_return_value(connection, ' && '.join(mount_commands))
        return self.log
