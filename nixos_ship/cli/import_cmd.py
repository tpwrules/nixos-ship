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
        "src_file", type=argparse.FileType("rb")
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
def compute_needed_paths(workdir, config_path, path_infos, store_root):
    print("Computing the set of paths which need to be imported...")

    # make gc roots for all the paths we have so we can be certain they won't go
    # away if there is gc activity
    gc_roots = workdir/"have_roots"
    root_i = 0

    path_info_map = {p.path: p for p in path_infos}

    needed_paths = {config_path: True} # keep as a dict to preserve order
    have_paths = set() # order doesn't matter
    # iterate through paths backwards so we can create roots for more of the
    # tree at a time
    for path_info in path_infos[::-1]:
        path = path_info.path
        if path not in needed_paths:
            continue

        root_i += 1
        # does this path exist in the store?
        exists = os.path.exists(store_root+path)
        if exists: # create a GC root so it won't get deleted out from under us
            exists = nix_tools.create_root_if_path_exists(
                path, gc_roots/f"r_{root_i}", store_root)
        if exists: # the GC root creation was successful and it still exists
            # so we can now be certain this path exists and we also have the
            # paths it references
            del needed_paths[path]
            have_paths.add(path)
            for reference in path_info.references:
                have_paths.add(reference)
        else:
            # we can now be certain this path doesn't exist and we still
            # need to search for the paths it references, assuming we don't
            # already know we have them. we know we haven't searched for them
            # because we are iterating in reverse topological order; this is
            # just an optimization to avoid creating so many GC roots
            for reference in path_info.references:
                if reference not in have_paths:
                    needed_paths[reference] = True

    # return the paths we don't have in the correct order
    return list(needed_paths.keys())[::-1]

def import_needed_paths(sf, path_list, path_infos, needed_paths, store_root):
    missing = False
    for path in needed_paths:
        if path not in path_list:
            print(f"error: missing path {path}")
            missing = True

    if missing:
        print("sorry, cannot import")
        return False

    with nix_store.LocalStore(store_root) as store:
        store_paths_file = sf.open_store_paths_file()
        needed_set = set(needed_paths)
        for path_info in path_infos:
            if path_info.path not in path_list:
                continue
            if path_info.path not in needed_set:
                store_paths_file.seek(path_info.nar_size, os.SEEK_CUR)
            else:
                print("importing", path_info.path)
                store.add_nar_from(path_info, store_paths_file)

        store_paths_file.close()

    return True

def import_handler(args):
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

        import_needed_paths(sf, path_list, path_infos, needed_paths, args.root)
