#!/usr/bin/env python

from setuptools import find_packages, setup

setup(
    name="nixos-ship",
    version="0.1.0",
    license="MIT",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "nixos-ship = nixos_ship:main",
        ]
    },
    install_requires=[
        "zstandard"
    ]
)
