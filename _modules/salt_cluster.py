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


def _get_passwd(profile, prof_dir='/etc/salt/cloud.profiles.d'):
    '''
    retrieve profile password from profile config
    '''
    for prof_file_name in os.listdir(prof_dir):
        with open(os.path.join(prof_dir, prof_file_name)) as prof_file:
            prof_data = yaml.load(prof_file.read())
            if profile in prof_data:
                return prof_data[profile]['password']

    error = 'Failed to retrieve password for {0} from cloud profiles, {1}'.format(profile, prof_dir)
    log.error(error)
    raise CommandExecutionError(error)


def _add_to_roster(name, host, user, passwd, roster):
    '''
    add a cloud instance to the cluster roster
    '''
    entry = textwrap.dedent('''\
        {0}:
          host: {1}
          user: {2}
          passwd: {3}'''.format(name, host, user, passwd))
    __salt__['state.single']('file.touch', roster, makedirs=True)
    __salt__['file.blockreplace'](roster,
             '##### begin {0}'.format(name),
             '##### end {0}'.format(name),
             entry,
             append_if_not_found=True)


def _rem_from_roster(name, roster):
    '''
    remove a cloud instance from the cluster roster
    '''
    # remove config block
    __salt__['file.blockreplace'](roster,
                                  '##### begin {0}'.format(name),
                                  '##### end {0}'.format(name))

    # remove block markers
    __salt__['file.replace'](roster,
                             r'^##### begin {0}$\n'.format(name),
                             '')
    __salt__['file.replace'](roster,
                             r'^##### end {0}$\n'.format(name),
                             '')


def create_node(name, profile, user='root', roster='/etc/salt/cluster/roster'):
    '''
    Create a cloud instance using salt-cloud and add it to the cluster roster

    .. code-block:: bash

        salt master-minion salt_cluster.create_node jmoney-master linode-centos-7 root /tmp/roster
    '''
    passwd = _get_passwd(profile)
    args = ['--no-deploy', '--profile', profile, name]

    try:
        info = json.loads(__salt__['cmd.run_stdout'](_cmd(*args)))
    except ValueError as value_error:
        raise CommandExecutionError('Could not read json from salt-cloud: {0}'.format(value_error))

    if name in info:
        state = info[name].get('state')
        if state == 'Running' or state == 3:
            _add_to_roster(name, info[name]['public_ips'][0], user, passwd, roster)
            return True

    error = 'Failed to create node {0} from profile {1}: {2}'.format(name, profile, info)
    log.error(error)
    return (False, error)


def destroy_node(name, roster='/etc/salt/cluster/roster'):
    '''
    Destroy a cloud instance using salt-cloud and remove it from the cluster roster

    .. code-block:: bash

        salt master-minion salt_cluster.destroy_node jmoney-master
    '''
    args = ['--destroy', name]

    try:
        info = json.loads(__salt__['cmd.run_stdout'](_cmd(*args)))
    except ValueError as value_error:
        raise CommandExecutionError('Could not read json from salt-cloud: {0}'.format(value_error))

    if isinstance(info, dict) and name in str(info):
        _rem_from_roster(name, roster)
        return True
    else:
        error = 'Failed to remove node {0}: {1}'.format(name, info)
        log.error(error)
        return (False, error)
