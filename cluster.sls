simple_cluster:
  - roster: /etc/salt/cluster/simple_cluster.roster
  - jmoney-cluster-master:
      profile: linode-centos-7
      role: master
      master_config:
        transport: tcp
  - jmoney-cluster-syndic:
      profile: linode-centos-7
      role: syndic
      syndic_config:
        transport: tcp
      master_config:
        transport: tcp
      minion_config:
        transport: tcp
        master: localhost
  - jmoney-cluster-minion:
      profile: linode-centos-7
      role: minion
      minion_config:
        transport: tcp
        master: jmoney-cluster-syndic
      grains:
        salt_cluster: True
