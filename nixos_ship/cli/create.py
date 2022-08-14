import json
import itertools

from ..workdir import Workdir

from .. import git_tools
from .. import nix_tools
from .. import shipfile
from .. import nix_store

def get_config_names(flake_path):
    return sorted(nix_tools.eval_flake(flake_path,
        "nixosConfigurations",
        "builtins.attrNames"))

def build_flake_configs(flake_path, config_names):
    config_paths = {}
    workdir = flake_path.parent

    for idx, name in enumerate(config_names):
        # symlink to an ordinal name in case there are any config names which
        # are troubling for the filesystem
        config_path = workdir/f"{flake_path.name}_configs"/f"config_{idx}"

        print(f"Building flake for config {name}...")
        nix_tools.build_flake(flake_path,
            f"nixosConfigurations.\"{name}\".config.system.build.toplevel",
            config_path)

        # resolve the symlink to get the actual store path
        config_paths[name] = str(config_path.resolve())

    return config_paths

def create_handler(args):
    source_rev = git_tools.get_commit(args.rev)

    with Workdir(autoprune=True) as workdir:
        flake_path = workdir/"worktree"
        git_tools.create_worktree(flake_path, source_rev)

        if args.delta is not None:
            delta_flake_path = workdir/"delta_worktree"
            git_tools.create_worktree(delta_flake_path,
                git_tools.get_commit(args.delta))

        config_names = get_config_names(flake_path)
        config_paths = build_flake_configs(flake_path, config_names)

        if args.delta is not None:
            delta_config_names = get_config_names(delta_flake_path)
            delta_config_paths = build_flake_configs(
                delta_flake_path, delta_config_names)

        sf = shipfile.ShipfileWriter(workdir/"shipfile", args.dest_file)

        with nix_store.LocalStore() as store:
            print("Computing set of paths to ship...")
            config_closures = {name: store.query_closure([path])
                for name, path in config_paths.items()}

            paths = set(itertools.chain(*config_closures.values()))
            path_infos = store.query_path_infos(list(paths))
            path_infos = nix_store.sort_path_infos(path_infos)

            if args.delta is not None:
                delta_config_closures = {name: set(store.query_closure([path]))
                    for name, path in delta_config_paths.items()}
                # if the new config has new systems, pretend there's nothing
                # from any old systems
                for name in config_closures.keys():
                    delta_config_closures.setdefault(name, set())

                # assume each system only has its delta system present, and not
                # other systems
                config_closures = {name:
                    [p for p in paths if p not in delta_config_closures[name]]
                    for name, paths in config_closures.items()
                }

                paths = set(itertools.chain(*config_closures.values()))

            path_info_file = sf.open_path_info_file()
            path_info_file.write(json.dumps({
                "config_paths":
                    {str(k): str(v) for k, v in config_paths.items()},
                "path_list": nix_store.sort_paths(list(paths)),
                "path_infos": [p._asdict() for p in path_infos],
            }, indent=2).encode('utf8'))
            path_info_file.close()

            print("Writing store paths...")
            store_paths_file = sf.open_store_paths_file(compression=args.level)
            for path_info in path_infos:
                if path_info.path in paths:
                    store.dump_nar_into(path_info.path, path_info.nar_size,
                        store_paths_file)
            store_paths_file.close()

        sf.close()
