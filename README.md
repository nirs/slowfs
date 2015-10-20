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
# mkdir mountpoint
# python slowfs.py /realfs /slowfs
```

You will see all files in /realfs under /slowfs. Manipulating the files
under slowfs will be slow as you configure in slowfs.py.

## Configuration

Nothing fancy yet; add sleeps in the oprations you want to be slow:

```python
    def unlink(self, path):
        time.sleep(60)
        return os.unlink(self._full_path(path))
```

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
