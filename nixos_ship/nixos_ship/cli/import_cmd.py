import json
import subprocess
import os

from ..workdir import Workdir

from .. import nix_tools
from .. import shipfile
from .. import nix_store

def build_import_parser(subparsers):
    import argparse

    import_parser = subparsers.add_parser(
        "import", help="import a shipfile"
    )

    import_parser.add_argument(
        "src_file", type=str
    )

    import_parser.add_argument("-n", "--name",
        type=str, help="name of configuration to import",
        default=open("/proc/sys/kernel/hostname", "r").read().strip()
    )

    import_parser.add_argument("--root",
        type=str, help="root of system to import configuration into",
        default=""
    )

    import_parser.set_defaults(handler=import_handler)
    return import_parser

# determine which paths we already have and which we need from this file
def compute_needed_paths(config_path, path_infos, store):
    print("Computing the set of paths which need to be imported...")

    # compute the closure of the config path
    path_info_map = {p.path: p for p in path_infos}
    check_paths = set([config_path])
    closure = set()
    while len(check_paths) > 0:
        # add the referrers of this path to the ones we need to check
        path = check_paths.pop()
        closure.add(path)

        curr_referrers = set(path_info_map[path].references)
        # remove paths already in the closure i.e. ones we already checked
        curr_referrers -= closure
        # remember paths we need to check for more paths in the closure
        check_paths |= curr_referrers

    valid_path_set = set(store.query_valid_paths(list(closure),
        lock=True, substitute=False)) # prevent valid paths from being GCd

    # return the paths we need but don't have in the correct order
    needed = closure - valid_path_set
    return [p.path for p in path_infos if p.path in needed]

def import_needed_paths(sf, path_list, path_infos, needed_paths, store):
    missing = False
    for path in needed_paths:
        if path not in path_list:
            print(f"error: missing path {path}")
            missing = True

    if missing:
        print("sorry, cannot import")
        return False

    needed_set = set(needed_paths)
    for path_info in path_infos:
        if path_info.path not in path_list:
            continue
        if path_info.path in needed_set:
            print("importing", path_info.path)
            sf.source_nar_into(path_info.nar_hash,
                lambda fp: store.sink_nar_from(path_info, fp))

    return True

def import_handler(args):
    with Workdir() as workdir, nix_store.LocalStore(args.root) as store:
        sf = shipfile.ShipfileReader(workdir/"shipfile", args.src_file)
        sf.check_version_info()

        sf.read_metadata()
        sf.read_store_metadata()

        path_infos = nix_store.sort_path_infos(sf.path_infos)
        path_list = set(sf.path_list)

        config_path = sf.config_info[args.name]
        needed_paths = compute_needed_paths(config_path, path_infos, store)

        import_needed_paths(sf, path_list, path_infos, needed_paths, store)
