import json
import subprocess
import os
import sys

from .. import nix_tools
from .. import shipfile
from .. import nix_store

from .import_cmd import do_import

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

    install_parser.add_argument("--switch", nargs="?",
        default="boot", const="switch", # no-arg-added default
        help="switch-to-configuration action (default boot, or switch if only "
        "flag specified)")

    install_parser.set_defaults(handler=install_handler)
    return install_parser

def install_handler(args):
    with nix_store.LocalStore(args.root) as store:
        # do the import so we have the path on disk to install
        success, config_path = do_import(store, args.src_file, args.name)

        if not success:
            sys.exit(1)

        print("import succeeded, doing installation...")

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

        print(f"running switch-to-configuration {args.switch}...")
        subprocess.run([
            *enter_cmd,
            config_path+"/bin/switch-to-configuration", args.switch
        ], check=True, env=env)

        print("install succeeded, please reboot")
