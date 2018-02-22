# -*- coding: utf-8 -*-
'''

'''
from __future__ import absolute_import

# Import python libs
import os
import yaml
import json
import logging
import textwrap

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError


log = logging.getLogger(__name__)
__outputter__ = {
    'create_node': 'highstate',
    'destroy_node': 'highstate',
}


def _cmd(*args):
    '''
    construct salt-cloud command
    '''
    cmd = ['salt-cloud', '--output=json', '--assume-yes']
    cmd.extend(args)
    return cmd


def _is_private_addr(ip_addr):
    '''
    test whether ip_addr is private according to RFC 1918
    '''
    ip = [int(quad) for quad in ip_addr.strip().split('.')]
    if ip[0] == 10:
        return True
    elif ip[0] == 172 and ip[1] in [i for i in range(16, 32)]:
        return True
    elif ip[0] == 192 and ip[1] == 168:
        return True


def _get_ip_addr(driver, info, name):
    '''
    retrieve IP address from info returned from driver
    '''
    if not name in info:
        return

    if driver == 'linode':
        state = info[name].get('state')
        if state == 'Running' or state == 3:
            for ip_addr in info[name]['public_ips']:
                if not _is_private_addr(ip_addr):
                    return salt.utils.to_str(ip_addr)
    elif driver == 'digital_ocean':
        if info[name].get('status') == 'new':
            for net in info[name]['networks']['v4']:
                if not _is_private_addr(net['ip_address']):
                    return salt.utils.to_str(net['ip_address'])
    elif driver == 'ec2':
        return salt.utils.to_str(info[name]['ipAddress'])
    elif driver == 'openstack':
        for ip_addr in info[name]['public_ips']:
            if salt.utils.network.is_ipv4(ip_addr):
                return salt.utils.to_str(ip_addr)
    elif driver == 'joyent':
        return salt.utils.to_str(info[name]['primaryIp'])


def _get_driver_creds(profile):
    '''
    retrieve password or ssh key from profile/provider
    '''
    def read_confs(cloud_dir, section):
        '''
        read through cloud config files
        '''
        for file_name in os.listdir(cloud_dir):
            with open(os.path.join(cloud_dir, file_name)) as file_:
                try:
                    data = yaml.load(file_.read())
                except yaml.reader.ReaderError:
                    continue

                if section in data:
                    return {'driver': data[section].get('driver'),
                            'provider': data[section].get('provider'),
                            'ssh_username': data[section].get('ssh_username'),
                            'password': data[section].get('password'),
                            'ssh_key_file': data[section].get('ssh_key_file'),
                            'private_key': data[section].get('private_key')}

        return {}

    # TODO: get these from __opts__
    conf_dir = '/etc/salt'
    prof_dir = os.path.join(conf_dir, 'cloud.profiles.d')
    prov_dir = os.path.join(conf_dir, 'cloud.providers.d')

    prof_data = read_confs(prof_dir, profile)
    prov_data = read_confs(prov_dir, prof_data.get('provider', ''))

    ret = {}
    if not prof_data or not prov_data:
        return ret  # couldn't find profile or provider data

    for item in ('ssh_username', 'password', 'ssh_key_file', 'private_key'):
        if prof_data[item]:
            ret[item] = prof_data[item]
        elif prov_data[item]:
            ret[item] = prov_data[item]
    ret['driver'] = prov_data['driver'] if prov_data['driver'] else prov_data['provider']
    return ret


def _add_to_roster(roster, name, host, user, auth, sudo):
    '''
    add a cloud instance to the cluster roster
    '''
    entry = {name: {'host': host, 'user': user}}
    entry[name].update(auth)
    if user != 'root' and sudo:
        entry[name].update({'sudo': True, 'tty': True})

    __salt__['state.single']('file.touch', roster, makedirs=True)
    __salt__['file.blockreplace'](roster,
                                  '# -- begin {0} --'.format(name),
                                  '# -- end {0} --'.format(name),
                                  yaml.dump(entry),
                                  append_if_not_found=True)


def _rem_from_roster(roster, name):
    '''
    remove a cloud instance from the cluster roster
    '''
    # remove config block
    __salt__['file.blockreplace'](roster,
                                  '# -- begin {0} --'.format(name),
                                  '# -- end {0} --'.format(name))

    # remove block markers
    __salt__['file.replace'](roster,
                             r'^# -- begin {0} --$\n'.format(name),
                             '')
    __salt__['file.replace'](roster,
                             r'^# -- end {0} --$\n'.format(name),
                             '')


def create_node(name, profile, user='root', roster='/etc/salt/roster', sudo=True):
    '''
    Create a cloud instance using salt-cloud and add it to the cluster roster

    .. code-block:: bash

        salt master-minion salt_cluster.create_node jmoney-master linode-centos-7 root /tmp/roster
    '''
    creds = _get_driver_creds(profile)

    if not creds:
        raise CommandExecutionError('Could not find profile or provider data for {0}'.format(profile))

    if 'driver' in creds:
        driver = creds['driver']
    else:
        raise CommandExecutionError('Could not find cloud driver info for {0}'.format(profile))

    if 'ssh_username' in creds:
        user = creds['ssh_username']

    if 'password' in creds:
        auth = {'passwd': creds['password']}
    elif 'ssh_key_file' in creds:
        auth = {'priv': creds['ssh_key_file']}
    elif 'private_key' in creds:
        auth = {'priv': creds['private_key']}
    else:
        raise CommandExecutionError('Could not find login auth info for {0}'.format(profile))

    ret = ''

    args = ['--no-deploy', '--profile', profile, name]
    res = __salt__['cmd.run_all'](_cmd(*args))

    # assume that the cloud response is a json object or list and strip any
    # non-json messages
    stdout = res['stdout'].splitlines()
    index = 0
    for index, line in enumerate(stdout):
        line = line.strip()
        if line.startswith('[') or line.startswith('{'):
            break
    ret += '\n'.join(stdout[:index])  # return message to user
    res['stdout'] = '\n'.join(stdout[index:])

    try:
        info = json.loads(res['stdout'])
    except (TypeError, ValueError) as error:
        raise CommandExecutionError('Could not read json from salt-cloud: {0}: {1}'.format(error, res['stderr']))

    ip_addr = _get_ip_addr(driver, info, name)
    if ip_addr:
        _add_to_roster(roster, name, ip_addr, user, auth, sudo)
        msg = 'Created node {0} from profile {1}'.format(name, profile)
        return '\n'.join([ret, msg])

    error = 'Failed to create node {0} from profile {1}: {2}'.format(name, profile, res['stderr'])
    log.error(error)
    return (False, error)


def destroy_node(name, roster='/etc/salt/roster'):
    '''
    Destroy a cloud instance using salt-cloud and remove it from the cluster roster

    .. code-block:: bash

        salt master-minion salt_cluster.destroy_node jmoney-master
    '''
    ret = ''

    args = ['--destroy', name]
    res = __salt__['cmd.run_all'](_cmd(*args))

    # assume that the cloud response is a json object or list and strip any
    # non-json messages
    stdout = res['stdout'].splitlines()
    index = 0
    for index, line in enumerate(stdout):
        line = line.strip()
        if line.startswith('[') or line.startswith('{'):
            break
    ret += '\n'.join(stdout[:index])  # return message to user
    res['stdout'] = '\n'.join(stdout[index:])

    try:
        info = json.loads(res['stdout'])
    except (TypeError, ValueError) as error:
        raise CommandExecutionError('Could not read json from salt-cloud: {0}: {1}'.format(error, res['stdout']))

    if isinstance(info, dict) and name in str(info):
        _rem_from_roster(roster, name)
        msg = 'Destroyed node {0}'.format(name)
        return '\n'.join([ret, msg])
    else:
        error = 'Failed to remove node {0}: {1}'.format(name, res['stderr'])
        log.error(error)
        return (False, error)
