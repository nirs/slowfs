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
and run the reload.py script:

```
python reload.py
```

Note: you must run this in the same directory you started slowfs.

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
