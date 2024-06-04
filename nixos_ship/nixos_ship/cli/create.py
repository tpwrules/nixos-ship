import json
import itertools
import re

from ..workdir import Workdir

from .. import git_tools
from .. import nix_tools
from .. import shipfile
from .. import nix_store

def build_create_parser(subparsers):
    import argparse

    def parse_size(size):
        size = size.strip()
        if len(size) == 0:
            raise ValueError("size must be specified")

        if size[-1] in "KMGT":
            # calculate multiplier by looking up string position
            multiplier = 2**(10*(" KMGT".index(size[-1])))
            size = size[:-1] # remove from number
        else:
            multiplier = 1

        size = int(float(size)*multiplier)

        if size <= 0:
            raise ValueError("size must be positive")

        return size

    create_parser = subparsers.add_parser(
        "create", help="create a shipfile")

    create_parser.add_argument(
        "dest_file", type=str
    )

    create_parser.add_argument(
        "--rev", type=str, default="HEAD",
        help="rev to create the shipfile from (defaults to HEAD)"
    )

    create_parser.add_argument(
        "--delta", type=str,
        help="rev we assume the recipient already has"
    )

    create_parser.add_argument(
        "--level", type=str, choices=["ultra", "normal", "fast"],
        default="normal",
        help="tune compression level for your patience"
    )

    create_parser.add_argument("-n", "--name",
        type=str, help="regex matching configuration names to ship", default=""
    )

    create_parser.add_argument("--split", type=parse_size,
        help="size of each shipfile part; supports KMGT as 2**10 suffixes",
    )

    create_parser.set_defaults(handler=create_handler)
    return create_parser

def get_config_names(flake_path, name_regex):
    names = nix_tools.eval_flake(flake_path,
        "nixosConfigurations",
        "builtins.attrNames")

    return sorted(n for n in names if name_regex.match(n) is not None)

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
    name_regex = re.compile(args.name)
    source_rev = git_tools.get_commit(args.rev)

    with Workdir(autoprune=True) as workdir:
        flake_path = workdir/"worktree"
        git_tools.create_worktree(flake_path, source_rev)

        if args.delta is not None:
            delta_flake_path = workdir/"delta_worktree"
            git_tools.create_worktree(delta_flake_path,
                git_tools.get_commit(args.delta))

        config_names = get_config_names(flake_path, name_regex)
        config_paths = build_flake_configs(flake_path, config_names)

        if args.delta is not None:
            delta_config_names = get_config_names(delta_flake_path, name_regex)
            delta_config_paths = build_flake_configs(
                delta_flake_path, delta_config_names)

        sf = shipfile.ShipfileWriter(workdir/"shipfile", args.dest_file,
            compression=args.level,
            split_size=args.split)
        sf.write_version_info()

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

            sf.write_config_info(config_paths)

            sf.write_store_info()
            for p in path_infos:
                sf.write_narinfo(p, in_file=p.path in paths)

            print("Writing store paths...")
            for path_info in path_infos:
                if path_info.path in paths:
                    store.source_nar_into(path_info.path, path_info.nar_size,
                        lambda nar_fp: sf.sink_nar_into(
                            path_info.nar_hash, path_info.nar_size, nar_fp))

        sf.close()
