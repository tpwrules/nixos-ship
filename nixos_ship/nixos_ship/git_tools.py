# functions for interacting with the git command line tools
import subprocess

# get the exact commit hash for the given commit-ish thing
def get_commit(commitish):
    try:
        proc = subprocess.run([
            "git", "rev-parse", "--verify", "--end-of-options",
            f"{commitish}^{{commit}}"
        ], check=True, stdout=subprocess.PIPE, text=True)
    except subprocess.CalledProcessError as e:
        raise ValueError(f"could not identify commit for '{commitish}'") from e

    return proc.stdout.strip()

# create a worktree directory containing the given commit for the git repo in
# the current directory
def create_worktree(workdir, commit):
    subprocess.run(["git", "worktree", "add", str(workdir), commit])

# delete all no-longer-visible worktrees
def prune_worktrees():
    subprocess.run(["git", "worktree", "prune"])
