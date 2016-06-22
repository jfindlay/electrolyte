# electrolyte

An acceptance testing framework for Salt in solution.

Electrolyte uses local salt-master and salt-minion daemons, the orchestrate
runner, and the salt reactor to create arbitrary salt clusters and run
acceptance tests on them.  Salt ssh minions connect to each VM in the salt
cluster and relay the acceptance tests to the cluster and their results back to
the salt master for processing.

Electrolyte requires salt-cloud credentials and configurations in order to
provision VMs.  In the future, support will be added for containers and local
VMs.
