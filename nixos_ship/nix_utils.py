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
