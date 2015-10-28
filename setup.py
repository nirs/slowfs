# Copyright (c) 2015, Nir Soffer
# Copyright (c) 2013, Stavros Korokithakis
# All rights reserved.
#
# Licensed under BSD licnese, see LICENSE.

from distutils.core import setup

setup(
    author="Nir Soffer",
    author_email="nsoffer@redhat.com",
    description=("A very slow file sysem for simulating overloded storage"),
    license="BSD",
    name="slowfs",
    py_modules = ["slowfs.py"],
    scripts=["slowfsctl"],
    url="https://github.com/nirs/slowfs",
    version="0.1",
)
