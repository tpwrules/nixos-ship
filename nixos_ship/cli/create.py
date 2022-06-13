import json
import itertools

from ..workdir import Workdir

from .. import git_utils
from .. import nix_utils
from .. import shipfile
from .. import nix_store

def get_config_names(flake_path):
    return nix_utils.eval_flake(flake_path,
        "nixosConfigurations",
        "builtins.attrNames")

def build_flake_configs(flake_path, config_names):
    config_paths = {}
    workdir = flake_path.parent

    for idx, name in enumerate(config_names):
        # symlink to an ordinal name in case there are any config names which
        # are troubling for the filesystem
        config_path = workdir/f"{flake_path.name}_configs"/f"config_{idx}"

        nix_utils.build_flake(flake_path,
            f"nixosConfigurations.\"{name}\".config.system.build.toplevel",
            config_path)

        # resolve the symlink to get the actual store path
        config_paths[name] = str(config_path.resolve())

    return config_paths

def create_handler(args):
    source_rev = git_utils.get_commit(args.rev)

    with Workdir() as workdir:
        flake_path = workdir/"worktree"
        git_utils.create_worktree(flake_path, source_rev)

        config_names = get_config_names(flake_path)
        config_paths = build_flake_configs(flake_path, config_names)

        sf = shipfile.ShipfileWriter(workdir/"shipfile", args.dest_file)

        with nix_store.LocalStore() as store:
            config_closures = {name: store.query_closure([path])
                for name, path in config_paths.items()}

            paths = set(itertools.chain(*config_closures.values()))
            path_infos = store.query_path_infos(list(paths))
            path_infos = nix_store.sort_path_infos(path_infos)

            path_info_file = sf.open_path_info_file()
            path_info_file.write(json.dumps({
                "config_paths":
                    {str(k): str(v) for k, v in config_paths.items()},
                "path_infos": [p._asdict() for p in path_infos],
            }, indent=2).encode('utf8'))
            path_info_file.close()

            store_paths_file = sf.open_store_paths_file()
            for path_info in path_infos:
                store.dump_nar_into(path_info.path, path_info.nar_size,
                    store_paths_file)
            store_paths_file.close()

        sf.close()
