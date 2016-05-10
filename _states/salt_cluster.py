# -*- coding: utf-8 -*-
'''
Create and destroy clusters of VMs.

Create two nodes:

.. code-block:: yaml

    master:
      salt_cluster.node_present:
        - name: jmoney-master
        - profile: linode-centos-7

    minion:
      salt_cluster.node_present:
        - name: jmoney-minion
        - profile: linode-ubuntu-15

Destroy two nodes:

.. code-block:: yaml

    master:
      salt_cluster.node_absent:
        - name: jmoney-master

    minion:
      salt_cluster.node_absent:
        - name: jmoney-minion
'''

# Import salt libs
from salt.exceptions import CommandExecutionError


# Import 3rd party libs
from salt.ext import six

__outputter__ = {
    'present': 'highstate',
    'absent': 'highstate',
}


def node_present(name, profile):
    '''
    Create a salt cluster node
    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    if __salt__['cloud.has_instance'](name):
        ret['result'] = True
        ret['comment'] = 'Cluster node {0} already present'.format(name)
        return ret
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Cluster node {0} is set to be created'.format(name)
        return ret

    try:
        info = __salt__['salt_cluster.create_node'](name, profile)
    except CommandExecutionError as err:
        info = (False, err)

    if isinstance(info, six.string_types):
        ret['changes'] = {'node': name}
        ret['result'] = True
        ret['comment'] = 'Cluster node {0} created from cloud profile {1}'.format(name, profile)
        return ret
    else:
        ret['result'] = False
        ret['comment'] = info[1]
        return ret


def node_absent(name):
    '''
    Destroy a salt cluster node
    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    if not __salt__['cloud.has_instance'](name):
        ret['result'] = True
        ret['comment'] = 'Cluster node {0} already absent'.format(name)
        return ret
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Cluster node {0} is set to be destroyed'.format(name)
        return ret

    try:
        info = __salt__['salt_cluster.destroy_node'](name)
    except CommandExecutionError as err:
        info = (False, err)

    if isinstance(info, six.string_types):
        ret['changes'] = {'node': name}
        ret['result'] = True
        ret['comment'] = 'Cluster node {0} destroyed'.format(name)
        return ret
    else:
        ret['result'] = False
        ret['comment'] = info[1]
        return ret


def present(name, profiles):
    '''
    Create a salt cluster with the nodes named under the profiles
    '''
    ret = {'name': name,
           'changes': {},
           'result': None if __opts__['test'] else False,
           'comment': ''}

    node_rets = []
    for prof_map in profiles:
        profile = prof_map.keys()[0]
        for node_name in prof_map[profile]:
            node_ret = node_present(node_name, profile)
            node_rets.append(node_ret)

            # changes
            if node_ret['changes']:
                if not 'nodes' in ret['changes']:
                    ret['changes']['nodes'] = []
                ret['changes']['nodes'].append(node_name)

            # result
            ret['result'] = ret['result'] or node_ret['result']

    # comment
    if ret['result']:
        if ret['changes']:
            ret['comment'] = 'Cluster {0} created'.format(name)
        else:
            ret['comment'] = 'Cluster {0} already present'.format(name)
    elif ret['result'] is None:
        ret['comment'] = 'Cluster {0} is set to be created'.format(name)
    else:
        ret['comment'] = 'Cluster {0} failed to be created: {1}'.format(name, [nr['comment'] for nr in node_rets])

    return ret


def absent(name, profiles):
    '''
    Destroy a salt cluster with the nodes named under the profiles
    '''
    ret = {'name': name,
           'changes': {},
           'result': None if __opts__['test'] else False,
           'comment': ''}

    node_rets = []
    for prof_map in profiles:
        profile = prof_map.keys()[0]
        for node_name in prof_map[profile]:
            node_ret = node_absent(node_name)
            node_rets.append(node_ret)

            # changes
            if node_ret['changes']:
                if not 'nodes' in ret['changes']:
                    ret['changes']['nodes'] = []
                ret['changes']['nodes'].append(node_name)

            # result
            ret['result'] = ret['result'] or node_ret['result']

    # comment
    if ret['result']:
        if ret['changes']:
            ret['comment'] = 'Cluster {0} destroyed'.format(name)
        else:
            ret['comment'] = 'Cluster {0} already absent'.format(name)
    elif ret['result'] is None:
        ret['comment'] = 'Cluster {0} is set to be destroyed'.format(name)
    else:
        ret['comment'] = 'Cluster {0} failed to be destroyed: {1}'.format(name, [nr['comment'] for nr in node_rets])

    return ret
