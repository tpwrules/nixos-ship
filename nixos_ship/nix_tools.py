# functions for interacting with the nix command line tools

import subprocess
import json

# evaluate some function (or the identity function by default) over an attribute
# of the given flake and return the resulting object
def eval_flake(flake_path, attr, fn="x: x"):
    proc = subprocess.run([
        "nix", "eval",
        "--extra-experimental-features", "nix-command",
        "--extra-experimental-features", "flakes",
        "--json",
        "--apply", fn,
        str(flake_path)+"#"+attr
    ], check=True, stdout=subprocess.PIPE, text=True)

    return json.loads(proc.stdout)

# build some attribute of the given flake and put a GC root in the specified
# location
def build_flake(flake_path, attr, gc_root):
    subprocess.run([
        "nix", "build",
        "--extra-experimental-features", "nix-command",
        "--extra-experimental-features", "flakes",
        "--out-link", str(gc_root),
        str(flake_path)+"#"+attr
    ], check=True)

# atomically create a GC root for the given store path at the given location
# if the store path exists. returns True if successful or False if the path
# did not exist
def create_root_if_path_exists(store_path, root, store_root=""):
    if root.exists() or root.is_symlink():
        raise ValueError(f"proposed GC root {root} already exists")

    try:
        subprocess.run([
            "nix-store",
            "--option", "substitute", "false",
            "--realise",
            "--add-root", str(root),
            "--store", store_root,
            store_path
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        # assume it failed because the path does not exist
        return False

    return True

# set the given profile's latest version to contain the given path
def set_profile_path(profile, path, store_root=""):
    subprocess.run([
        "nix-env",
        "--profile", str(profile),
        "--set", path,
        "--store", store_root,
    ], check=True, stdout=subprocess.DEVNULL)
