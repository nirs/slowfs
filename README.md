# slowfs
A very slow file system for simulating overloaded storage

## Installation

```
# dnf install fuse fuse-devel
# git clone https://github.com/nirs/slowfs.git
# cd slowfs
# pip install -r requirements.txt
```

## Usage

```
# mkdir /realfs /slowfs
# python slowfs.py -c slowfs.cfg /realfs /slowfs
```

You will see all files in /realfs under /slowfs. Manipulating the files
under slowfs will be slow as you configure in slowfs.cfg

## Configuration

The config file is a Python module, with key value pairs for all fuse
operations.

Example: adding delay of 60 seconds when removing a file:
```python
# slowfs.cfg
unlink = 60
```

Operations without configuration use no delay. See `slowfs.cfg.example` for
more info.

To change configuration when the mount is online, edit the configuration file
and reload the configuration:

```
./slowfsctl reload
```

Note: you must run this in the same directory you started slowfs. slowfsctl
uses the "control" socket created by slowfs in the worrking directory.

## Controlling slowfs

You can use `slowfsctl` tool to modify slowfs without restarting it.

Available comamnds:

- help
- status
- disable
- enable
- reload
- get
- set
- log

### help
```
slowfsctl help
```
Print available commands

### status
```
slowfsctl status
```
Print current status (Enabled, Disable)

### disable
```
slowfsctl disable
```
Disable current configuration, deactivating all delays.

### enable
```
slowfsctl enable
```
Enable current configuration, activating all delays

### reload
```
slowfsctl reload
```
Reload configuration from cofiguration file specified using the -c, --config
option. If slowfs is running without configuration file, reset configuration to
defaults.

### get
```
slowfsctl get NAME
```
Print current delay for fuse operation NAME.

### set
```
slowfsctl set NAME VALUE
```
Set dealy for fuse opration NAME to VALUE, overriding value read form
configuration file.

### log
```
slowfsctl log LEVEL
```
Change logging level to (debug, info, warning, error)

Note: debug log level is extermely detailed and slow, logging every read or
written to storage, generating gigabytes of logs.

## Exporting via NFS

Assuming you mounted your slowfs filesystem on /slowfs

Edit /etc/exports and add:
```
/slowfs    *(rw,sync,no_subtree_check,anonuid=36,anongid=36,fsid=0)
```

Notes:
- fsid=NNN is required
- anonid=36,anongid=36 - required for ovirt
- seems that all_squash does not work with fuse

Restart nfs service:
```
systemctl restart nfs
```

Testing the mount on the client side:
```
# mkdir mountpoint
# mount -t nfs my.server.name:/slowfs mountpoint
# touch mnt/test
# time rm mnt/test
# time rm mnt/test

real    1m0.063s
user    0m0.000s
sys     0m0.001s
```

Note: unlink() was configured with 60 seconds sleep.


## Talks

- [slowfs - slowing down storage for fun and profit](https://nirs.github.io/slowfs-qecamp)
at QeCamp TLV 2017
