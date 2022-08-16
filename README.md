# nixos-ship

Generate and install complete flake-based NixOS configurations as highly compressed single files.

## Warning

This is beta software. While we believe the [shipfile format](./docs/format.md) to be stable and future-compatible, we have not proved this in practice.

## Basic Usage
```
machine-1$ cd some-dir-with-flake-nix
# create a shipfile from the a specific git rev which contains all its nixosConfigurations
machine-1$ nixos-ship --rev v1.0.0 ../configurations.shf
# communicate via e.g. sneakernet to machine 2 and install the configuration named
# machine-2 (or that machine's hostname by default)
machine-2$ nixos-ship install ../configurations.shf -n machine-2


# make some change and create a delta shipfile.
machine-1$ nixos-ship --rev v1.0.1 ../configurations_new.shf --delta v1.0.0
# communicate via e.g. sneakernet to machine 2.
# delta shipfile will be installable as long as the previous configuration
# is still in the store.
machine-2$ nixos-ship install ../configurations_new.shf
```

## Credits
This project is licensed under the MIT license.

This project uses [python-zstandard](https://github.com/indygreg/python-zstandard/), which is licensed under the 3-clause BSD license.

Significant inspiration for the code structure was derived from [nixpkgs-review](https://github.com/Mic92/nixpkgs-review).
