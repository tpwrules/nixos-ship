from ..workdir import Workdir

from .. import git_utils
from .. import nix_utils

def create_handler(args):
    source_rev = git_utils.get_commit(args.rev)

    with Workdir() as workdir:
        flake_path = workdir/"worktree"
        git_utils.create_worktree(flake_path, source_rev)

        # get the list of nixos configuration names
        conf_names = nix_utils.eval_flake(flake_path,
            "nixosConfigurations",
            "builtins.attrNames")

        for idx, name in enumerate(conf_names):
            # build each system configuration
            nix_utils.build_flake(flake_path,
                f"nixosConfigurations.\"{name}\".config.system.build.toplevel",
                workdir/f"system_{idx}")

        print(conf_names)
