# Copyright (c) 2015, Nir Soffer
# Copyright (c) 2013, Stavros Korokithakis
# All rights reserved.
#
# Licensed under BSD licnese, see LICENSE.

import argparse
import atexit
import errno
import logging
import os
import socket
import sys
import threading
import time

import fuse


def main(args):
    args = parse_args(args)
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO,
                        format='%(asctime)s %(levelname)s [%(name)s] %(message)s')
    if args.config:
        config = Config(args.config)
        Reloader(config)
    else:
        config = None
    ops = SlowFS(args.root, args.mountpoint, config)
    fuse.FUSE(ops, args.mountpoint, nothreads=True, foreground=True)


def parse_args(args):
    parser = argparse.ArgumentParser(description='A slow filesystem.')
    parser.add_argument('-c', '--config',
                        help='path to configuration file')
    parser.add_argument('--debug', action='store_true',
                        help=('enable extremely detailed and slow debug mode, '
                              'creating gigabytes of logs'))
    parser.add_argument('root', help='path to real file system')
    parser.add_argument('mountpoint', help='where to mount slowfs')
    return parser.parse_args(args)


class Config(object):

    def __init__(self, path):
        self._path = path
        self._namespace = {}
        self._load()

    def _load(self):
        d = {}
        with open(self._path) as f:
            exec f in d, d
        self._namespace = d

    def __getattr__(self, name):
        try:
            return self._namespace[name]
        except KeyError:
            raise AttributeError(name)


class Reloader(object):

    SOCK = "control"
    log = logging.getLogger("ctl")

    def __init__(self, config):
        self.config = config
        self._remove_sock()
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.sock.bind(self.SOCK)
        atexit.register(self._remove_sock)
        self.thread = threading.Thread(target=self._run)
        self.thread.daemon = True
        self.thread.start()

    def _run(self):
        try:
            while True:
                self._wait_for_reload()
        except Exception:
            self.log.exception("Unhnadled error")
            raise

    def _wait_for_reload(self):
        try:
            self.sock.recvfrom(128)
        except socket.error, e:
            self.log.error("Error receiving from control socket: %s", e)
        else:
            self.log.info("Loading configuration")
            try:
                self.config._load()
            except Exception:
                self.log.exception("Error reloading configuration")

    def _remove_sock(self):
        try:
            os.unlink(self.SOCK)
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise


class SlowFS(fuse.Operations):

    log = logging.getLogger("fs")

    def __init__(self, root, mountpoint, config):
        self.root = root
        self.mountpoint = mountpoint
        self.config = config

    def __call__(self, op, path, *args):
        if not hasattr(self, op):
            raise FuseOSError(EFAULT)
        self.log.debug('-> %s %r %r', op, path, args)
        seconds = getattr(self.config, op, 0)
        if seconds:
            time.sleep(seconds)
        try:
            ret = getattr(self, op)(path, *args)
        except Exception as e:
            self.log.debug('<- %s <error %s>', op, e)
            raise
        self.log.debug('<- %s %r', op, ret)
        return ret

    # Filesystem methods

    def access(self, path, mode):
        full_path = self._full_path(path)
        if not os.access(full_path, mode):
            raise fuse.FuseOSError(errno.EACCES)

    def chmod(self, path, mode):
        full_path = self._full_path(path)
        return os.chmod(full_path, mode)

    def chown(self, path, uid, gid):
        full_path = self._full_path(path)
        return os.chown(full_path, uid, gid)

    def getattr(self, path, fh=None):
        full_path = self._full_path(path)
        st = os.lstat(full_path)
        return dict((key, getattr(st, key)) for key in ('st_atime', 'st_ctime',
                     'st_gid', 'st_mode', 'st_mtime', 'st_nlink', 'st_size', 'st_uid'))

    def readdir(self, path, fh):
        full_path = self._full_path(path)

        dirents = ['.', '..']
        if os.path.isdir(full_path):
            dirents.extend(os.listdir(full_path))
        for r in dirents:
            yield r

    def readlink(self, path):
        target = os.readlink(self._full_path(path))
        if target.startswith(self.root):
            target = os.path.relpath(target, self.root)
            return os.path.join(self.mountpoint, target)
        else:
            return target

    def mknod(self, path, mode, dev):
        return os.mknod(self._full_path(path), mode, dev)

    def rmdir(self, path):
        full_path = self._full_path(path)
        return os.rmdir(full_path)

    def mkdir(self, path, mode):
        return os.mkdir(self._full_path(path), mode)

    def statfs(self, path):
        full_path = self._full_path(path)
        stv = os.statvfs(full_path)
        return dict((key, getattr(stv, key)) for key in ('f_bavail', 'f_bfree',
            'f_blocks', 'f_bsize', 'f_favail', 'f_ffree', 'f_files', 'f_flag',
            'f_frsize', 'f_namemax'))

    def unlink(self, path):
        return os.unlink(self._full_path(path))

    def symlink(self, name, target):
        if target.startswith(self.mountpoint):
            target = os.path.relpath(target, self.mountpoint)
            target = self._full_path(target)
        return os.symlink(target, self._full_path(name))

    def rename(self, old, new):
        return os.rename(self._full_path(old), self._full_path(new))

    def link(self, name, target):
        return os.link(self._full_path(target), self._full_path(name))

    def utimens(self, path, times=None):
        return os.utime(self._full_path(path), times)

    # File methods

    def open(self, path, flags):
        full_path = self._full_path(path)
        return os.open(full_path, flags)

    def create(self, path, mode, fi=None):
        full_path = self._full_path(path)
        return os.open(full_path, os.O_WRONLY | os.O_CREAT, mode)

    def read(self, path, length, offset, fh):
        os.lseek(fh, offset, os.SEEK_SET)
        return os.read(fh, length)

    def write(self, path, buf, offset, fh):
        os.lseek(fh, offset, os.SEEK_SET)
        return os.write(fh, buf)

    def truncate(self, path, length, fh=None):
        full_path = self._full_path(path)
        with open(full_path, 'r+') as f:
            f.truncate(length)

    def flush(self, path, fh):
        return os.fsync(fh)

    def release(self, path, fh):
        return os.close(fh)

    def fsync(self, path, fdatasync, fh):
        return self.flush(path, fh)

    # Helpers

    def _full_path(self, partial):
        if partial.startswith("/"):
            partial = partial[1:]
        return os.path.join(self.root, partial)


if __name__ == '__main__':
    main(sys.argv[1:])
