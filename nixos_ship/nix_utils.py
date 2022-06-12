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

