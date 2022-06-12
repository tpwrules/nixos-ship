import json
import subprocess

from ..workdir import Workdir

from .. import nix_utils
from .. import shipfile

def install_handler(args):
    with Workdir() as workdir:
        sf = shipfile.ShipfileReader(workdir/"shipfile", args.src_file)

        path_info_file = sf.open_path_info_file()
        path_info = json.loads(path_info_file.read().decode('utf8'))
        path_info_file.close()

        config_paths = path_info["config_paths"]
        export_paths = path_info["export_paths"]
        config_graphs = path_info["config_graphs"]

        config_path = config_paths[args.name]

        config_exists = nix_utils.create_root_if_path_exists(
            config_path, workdir/"config_root")

        if not config_exists:
            store_paths_file = sf.open_store_paths_file()
            nix_utils.import_store_paths(store_paths_file)
            store_paths_file.close()

        nix_utils.set_profile_path("/nix/var/nix/profiles/system", config_path)

        subprocess.run([
            config_path+"/bin/switch-to-configuration", "boot"
        ], check=True)
