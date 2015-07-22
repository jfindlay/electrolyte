# precipitate

An acceptance testing framework for Salt.

Precipitate uses local salt-master and salt-minion daemons, the orchestrate
runner, and the salt reactor to create arbitrary salt clusters and run
acceptance tests on them.  Salt ssh minions connect to each VM in the salt
cluster and relay the acceptance tests and their results back to the salt
master for processing.

Precipitate requires salt-cloud credentials and configurations in order to
provision VMs.  In the future, support will be added for containers and local
VMs.
