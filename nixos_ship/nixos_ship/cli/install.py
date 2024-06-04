import json
import subprocess
import os

from ..workdir import Workdir

from .. import nix_tools
from .. import shipfile
from .. import nix_store

from .import_cmd import compute_needed_paths, import_needed_paths

def build_install_parser(subparsers):
    import argparse

    install_parser = subparsers.add_parser(
        "install", help="install a shipfile"
    )

    install_parser.add_argument(
        "src_file", type=str
    )

    install_parser.add_argument("-n", "--name",
        type=str, help="name of configuration to install",
        default=open("/proc/sys/kernel/hostname", "r").read().strip()
    )

    install_parser.add_argument("--root",
        type=str, help="root of system to install configuration into",
        default=""
    )

    install_parser.add_argument("--install-bootloader",
        action="store_true", help="force install system bootloader")

    install_parser.set_defaults(handler=install_handler)
    return install_parser

def install_handler(args):
    with Workdir() as workdir, nix_store.LocalStore(args.root) as store:
        sf = shipfile.ShipfileReader(workdir/"shipfile", args.src_file)
        sf.check_version_info()

        sf.read_metadata()
        sf.read_store_metadata()

        path_infos = nix_store.sort_path_infos(sf.path_infos)
        path_list = set(sf.path_list)

        config_path = sf.config_info[args.name]
        needed_paths = compute_needed_paths(config_path, path_infos, store)

        import_successful = import_needed_paths(
            sf, path_list, path_infos, needed_paths, store)

        if import_successful:
            nix_tools.set_profile_path(args.root+"/nix/var/nix/profiles/system",
                config_path, args.root)

            enter_cmd = []
            if args.root != "":
                # convince nix tooling this is a nixos partition
                try:
                    os.mkdir(args.root+"/etc")
                except FileExistsError:
                    pass
                open(args.root+"/etc/NIXOS", "w").close()

                subprocess.run([ # from nixos-install, for grub
                    "ln", "-sfn", "/proc/mounts", args.root+"/etc/mtab"
                ], check=True)
                enter_cmd = ["nixos-enter", "--root", args.root, "--"]

            env = os.environ.copy()
            if args.install_bootloader:
                env["NIXOS_INSTALL_BOOTLOADER"] = "1"

            subprocess.run([
                *enter_cmd,
                config_path+"/bin/switch-to-configuration", "boot"
            ], check=True, env=env)

            print("install succeeded, please reboot")
