# Install cluster

Right now, Slurmpilot allows to install cluster by calling

```bash
slurmpilot --add-cluster
```

It then prompts the user for the cluster name, hostname, username, account, default partition, and remote path.
The user can also choose to prompt for a login password or passphrase for ssh if they set a key password.

This requires to have setup the ssh host, for instance

```bash
# ~/.ssh/config
Host clustername
	HostName clustername.domain.com
	User USER_NAME_ON_CLUSTER
	IdentityFile ~/.ssh/clustername  # possibly an ssh key for the given cluster
	ControlMaster auto  # keep the connection alive
	ControlPath ~/.ssh/ssh_%h_%p_%r
    ControlPersist 60m
```

We could propose to the user to add this automatically so they don't have to do it manually.
We would then be able to test their ssh connection to see if the host is available.

We would probably need to:

* backup the `~/.ssh/config` file
* append to the file
* warn the user if clustername is already present

Optionally, we could allow to do something like:

```
sp --helloworld clustername
```

which would run a simple hello world script on the cluster.