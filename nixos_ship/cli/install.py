import json
import subprocess
import os

from ..workdir import Workdir

from .. import nix_tools
from .. import shipfile
from .. import nix_store

from .import_cmd import compute_needed_paths, import_needed_paths

def install_handler(args):
    with Workdir() as workdir:
        sf = shipfile.ShipfileReader(workdir/"shipfile", args.src_file)

        path_info_file = sf.open_path_info_file()
        path_info = json.loads(path_info_file.read().decode('utf8'))
        path_info_file.close()

        config_paths = path_info["config_paths"]
        path_infos = nix_store.sort_path_infos([
            nix_store.PathInfo(**p) for p in path_info["path_infos"]])
        path_list = set(path_info["path_list"])

        config_path = config_paths[args.name]
        needed_paths = compute_needed_paths(
            workdir, config_path, path_infos, args.root)

        import_successful = import_needed_paths(
            sf, path_list, path_infos, needed_paths, args.root)

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
