import json

from ..workdir import Workdir

from .. import git_utils
from .. import nix_utils
from .. import shipfile

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
        config_paths[name] = config_path.resolve()

    return config_paths

def compute_export_paths(config_graphs):
    seen_paths = set()

    # build a list instead of a set of results so that we preserve order and
    # don't harm reproducibility
    export_paths = []
    for config_graph in config_graphs.values():
        for path in config_graph.keys():
            if path not in seen_paths:
                seen_paths.add(path)
                export_paths.append(path)

    return export_paths

def create_handler(args):
    source_rev = git_utils.get_commit(args.rev)

    with Workdir() as workdir:
        flake_path = workdir/"worktree"
        git_utils.create_worktree(flake_path, source_rev)

        config_names = get_config_names(flake_path)
        config_paths = build_flake_configs(flake_path, config_names)
        config_graphs = {name: nix_utils.get_path_references(path)
            for name, path in config_paths.items()}
        export_paths = compute_export_paths(config_graphs)

        sf = shipfile.ShipfileWriter(workdir/"shipfile", args.dest_file)

        store_paths_file = sf.open_store_paths_file()
        nix_utils.export_store_paths(export_paths, store_paths_file)
        store_paths_file.close()

        path_info_file = sf.open_path_info_file()
        path_info_file.write(json.dumps({
            "config_paths": {str(k): str(v) for k, v in config_paths.items()},
            "export_paths": export_paths,
            "config_graphs": config_graphs,
        }, sort_keys=True, indent=2).encode('utf8'))

        path_info_file.close()
