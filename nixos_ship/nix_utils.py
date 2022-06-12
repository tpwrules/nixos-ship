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

# get the graph of path references for a given store path
def get_path_references(store_path):
    proc = subprocess.run([
        "nix-store",
        "--query",
        "--graph",
        store_path
    ], check=True, stdout=subprocess.PIPE, text=True)

    graph = {}
    for line in proc.stdout.split("\n"):
        # reject starting, ending, and blank lines
        if line == "" or not line[0] == '"':
            continue

        if "->" in line:
            # parse line of form "path_from" -> "path_to" [stuff];
            path_from, _, path_to, *_ = line.split()
            path_from = f"/nix/store/{path_from[1:-1]}"
            path_to = f"/nix/store/{path_to[1:-1]}"

            graph[path_to].append(path_from)
        else:
            # parse line of form "path" [stuff];
            path, *_ = line.split()
            path = f"/nix/store/{path[1:-1]}"

            graph[path] = []

    return graph

# export some store paths
def export_store_paths(store_paths, dest):
    proc = subprocess.Popen([
        "nix-store",
        "--export",
        *store_paths
    ], stdout=subprocess.PIPE)

    buf = bytearray(1048576)
    while True:
        n = proc.stdout.readinto(buf)
        if n == 0:
            break

        dest.write(buf[:n])

    if proc.wait() > 0:
        raise subprocess.CalledProcessError()

# import some store paths
def import_store_paths(src):
    proc = subprocess.Popen([
        "nix-store",
        "--import"
    ], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL)

    buf = bytearray(1048576)
    while True:
        n = src.readinto(buf)
        if n == 0:
            break

        proc.stdin.write(buf[:n])

    proc.stdin.close()

    if proc.wait() > 0:
        raise subprocess.CalledProcessError()

# atomically create a GC root for the given store path at the given location
# if the store path exists. returns True if successful or False if the path
# did not exist
def create_root_if_path_exists(store_path, root):
    if root.exists() or root.is_symlink():
        raise ValueError(f"proposed GC root {root} already exists")

    try:
        subprocess.run([
            "nix-store",
            "--option", "substitute", "false",
            "--realise",
            "--add-root", str(root),
            store_path
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        # assume it failed because the path does not exist
        return False

    return True

# set the given profile's latest version to contain the given path
def set_profile_path(profile, path):
    subprocess.run([
        "nix-env",
        "--profile", str(profile),
        "--set", path
    ], check=True, stdout=subprocess.DEVNULL)
