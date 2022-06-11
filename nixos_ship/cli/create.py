from ..workdir import Workdir

from .. import git_utils
from .. import nix_utils

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

def create_handler(args):
    source_rev = git_utils.get_commit(args.rev)

    with Workdir() as workdir:
        flake_path = workdir/"worktree"
        git_utils.create_worktree(flake_path, source_rev)

        config_names = get_config_names(flake_path)
        config_paths = build_flake_configs(flake_path, config_names)

        print(config_paths)
