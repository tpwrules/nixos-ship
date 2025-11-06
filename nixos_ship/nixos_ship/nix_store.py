from enum import IntEnum
from dataclasses import dataclass, asdict
import subprocess
import os
import select
import hashlib

# read/write size used communicating with store (not a part of the protocol)
CHUNKSIZE = 131072

SERVE_MAGIC_1 = 0x390c9deb
SERVE_MAGIC_2 = 0x5452eecb

PROTOCOL_VERSION = (2 << 8) | 7

class ServeCommand(IntEnum):
    QUERY_VALID_PATHS = 1
    QUERY_PATH_INFOS = 2
    DUMP_STORE_PATH = 3
    IMPORT_PATHS = 4
    EXPORT_PATHS = 5
    BUILD_PATHS = 6
    QUERY_CLOSURE = 7
    BUILD_DERIVATION = 8
    ADD_TO_STORE_NAR = 9

@dataclass(frozen=True)
class PathInfo:
    path: str
    deriver: str
    references: list[str]
    nar_size: int
    nar_hash: str
    ca_info: str
    sigs: list[str]

    def _asdict(self):
        return asdict(self)

def sort_paths(paths):
    # first sort by name, then hash
    return sorted(paths, key=lambda p: (p[44:], p[:43]))

# sort path infos into topological order
def sort_path_infos(path_infos):
    paths = sort_paths(p.path for p in path_infos)
    path_info_map = {p.path: p for p in path_infos}

    sorted_path_infos = []
    seen_paths = set()
    def dfs(path_info):
        if path_info.path in seen_paths:
            return
        seen_paths.add(path_info.path)

        for reference in path_info.references:
            dfs(path_info_map[reference])

        sorted_path_infos.append(path_info)

    for path in paths:
        dfs(path_info_map[path])

    return sorted_path_infos

def nix_base32(b):
    ALPHABET = "0123456789abcdfghijklmnpqrsvwxyz"

    syms = (len(b)*8+4)//5
    bits = int.from_bytes(b, "little")
    chars = []
    for _ in range(syms):
        chars.append(ALPHABET[bits & 0x1F])
        bits >>= 5

    return "".join(chars)[::-1]

# something went wrong interacting with the store
class StoreError(RuntimeError):
    pass

# can be opened and closed multiple times
class StoreProcess:
    def __init__(self, store_root):
        self._store_root = store_root

        self._subp = None

    def open(self):
        # open and return (fin, fout)

        if self._subp is not None:
            raise RuntimeError("already open")

        self._subp = subprocess.Popen([
            "nix-store", "--serve", "--write",
            "--store", self._store_root,
        ], stdin=subprocess.PIPE, stdout=subprocess.PIPE)

        return self._subp.stdout, self._subp.stdin

    def close(self):
        if self._subp is None:
            return

        self._subp.stdin.close()
        self._subp.stdout.close()
        self._subp.wait()

        self._subp = None

class LocalStore:
    def __init__(self, store_root=""):
        self._proc = StoreProcess(store_root)
        self._store_root = store_root

    def __enter__(self):
        c = None
        try:
            c = StoreCommunicator(self._proc)
        finally:
            # context exit is not called if enter throws, so ensure store is
            # closed if the communicator fails to start.
            if c is None:
                self._proc.close()

        return c

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._proc.close()

class StoreCommunicator:
    def __init__(self, proc):
        self._proc = proc

        self._buf = memoryview(bytearray(CHUNKSIZE))

        self._open_store()

    def _open_store(self):
        self._fin, self._fout = self._proc.open()

        # send hellos
        self._write_num(SERVE_MAGIC_1)
        self._fout.flush()

        store_magic = self._read_num()
        self._ver = self._read_num()
        self._ver_minor = self._ver & 0xFF
        self._write_num(PROTOCOL_VERSION)
        self._fout.flush()

        if store_magic != SERVE_MAGIC_2:
            raise ValueError(f"store gave invalid magic: {store_magic}")

        if (self._ver & 0xFF00) != (PROTOCOL_VERSION & 0xFF00):
            raise ValueError(f"unsupported store major protocol version")

    def _read_num(self):
        return int.from_bytes(self._fin.read(8), "little")

    def _write_num(self, num):
        self._fout.write(num.to_bytes(8, "little"))

    def _read_string(self):
        blob_len = self._read_num()
        blob = self._fin.read(blob_len)
        if blob_len % 8 > 0:
            self._fin.read(8-(blob_len%8))
        return blob.decode("utf8")

    def _write_string(self, string):
        blob = string.encode("utf8")
        self._write_num(len(blob))
        self._fout.write(blob)
        if len(blob) % 8 > 0:
            self._fout.write(b"\x00"*(8-(len(blob)%8)))

    def _read_strings(self):
        num_strings = self._read_num()
        strings = []
        for path_i in range(num_strings):
            strings.append(self._read_string())
        return strings

    def _write_strings(self, strings):
        self._write_num(len(strings))
        for string in strings:
            self._write_string(string)

    def query_valid_paths(self, paths, lock=True, substitute=False):
        self._write_num(ServeCommand.QUERY_VALID_PATHS)
        self._write_num(int(bool(lock)))
        self._write_num(int(bool(substitute)))
        self._write_strings(paths)
        self._fout.flush()

        return self._read_strings()

    def query_closure(self, paths, include_outputs=False):
        self._write_num(ServeCommand.QUERY_CLOSURE)
        self._write_num(int(bool(include_outputs)))
        self._write_strings(paths)
        self._fout.flush()

        return self._read_strings()

    def query_path_infos(self, paths):
        self._write_num(ServeCommand.QUERY_PATH_INFOS)
        self._write_strings(paths)
        self._fout.flush()

        path_infos = []
        while True:
            path = self._read_string()
            if path == "":
                break

            deriver = self._read_string()
            references = sort_paths(self._read_strings())

            nar_size = self._read_num()
            self._read_num() # nar_size again
            nar_hash = self._read_string()

            ca_info = self._read_string()
            sigs = sorted(self._read_strings())

            path_infos.append(PathInfo(
                path=path,
                deriver=deriver,
                references=references,
                nar_size=nar_size,
                nar_hash=nar_hash,
                ca_info=ca_info,
                sigs=sigs,
            ))

        return path_infos

    def source_nar_fp(self, path, nar_hash, nar_size, fp):
        # read a nar from the store, taking an fp into which nar data is written

        hash_type, hash_expected = nar_hash.split(":")
        if hash_type == "sha256":
            # a slight fib but if nix uses it we kinda have to
            hasher = hashlib.sha256(usedforsecurity=False)
        else:
            raise ValueError(f"unknown hash type {hash_type}")


        self._write_num(ServeCommand.DUMP_STORE_PATH)
        self._write_string(path)
        self._fout.flush()

        # though we expect a certain size, the nar is serialized as we read it
        # so if there corruption it may end up too small or too large.

        # if the corrupt nar is the same size as the good nar, the hash check
        # will fail. if it's larger, the hash check will also fail, as a length
        # must have increased in the prefix we hash to make it bigger, causing
        # the prefix to differ. in the larger case, we won't correctly
        # calculate the current hash of the nar as we ignore the extra bytes,
        # but this is not a big deal.

        # small is the hard case as we may wait for more nar forever. work
        # around this by closing the store process out pipe if there is a long
        # read delay, causing it to close the in pipe after it finishes the nar
        # and stop our reads if we are expecting more than it will provide. if
        # it was just busy and gives us enough, we restart it and carry on.

        fin = self._fin
        fd = fin.fileno()

        # set up poll object to do the timeout
        poller = select.poll()
        poller.register(fd, select.POLLIN)

        fout_closed = False # did we close the fout pipe?
        try:
            os.set_blocking(fd, False) # make fin pipe nonblocking

            buf = self._buf
            buf_size = len(buf)
            size = nar_size
            while size > 0:
                num_read = fin.readinto(buf[:min(size, buf_size)])
                if num_read is None: # no data?
                    events = poller.poll(1000) # wait for 1 second
                    if len(events) == 0 and not fout_closed: # still no data :(
                        # close fout to cause store to close its end of fin
                        # after it's done sending so we die reading too much.
                        self._fout.close()
                        fout_closed = True
                    continue
                elif num_read == 0:
                    # end of file which we shouldn't see unless reading too much
                    raise StoreError("corrupt nar: unexpected end")

                part = buf[:num_read]
                hasher.update(part)
                fp.write(part)
                size -= num_read
        finally:
            if fout_closed:
                poller.unregister(fd) # don't leave soon-to-be-closed fd around
                self._proc.close() # close store fully
                self._open_store() # reopen the store (with blocking read pipe)
            else:
                os.set_blocking(fd, True) # make read pipe blocking again

        hash_got = nix_base32(hasher.digest())
        if hash_got != hash_expected:
            # we don't know the actual hash since we may have truncated it, so
            # don't bother say it
            raise StoreError(f"corrupt nar: bad hash, expected {nar_hash}")

    def sink_nar_fp(self, path_info, fp):
        # write a nar into the store, taking an fp which the nar data is read
        # out of
        self._write_num(ServeCommand.ADD_TO_STORE_NAR)
        self._write_string(path_info.path)
        self._write_string(path_info.deriver)
        self._write_string(path_info.nar_hash)
        self._write_strings(path_info.references)
        self._write_num(0) # registrationTime
        self._write_num(path_info.nar_size)
        self._write_num(0) # ultimate: did we actually build this nar?
        self._write_strings(path_info.sigs)
        self._write_string(path_info.ca_info)

        size = path_info.nar_size
        read = fp.read # for some extra speed
        write = self._fout.write
        while size > 0:
            data = read(min(size, CHUNKSIZE))
            data_len = len(data)
            if data_len == 0:
                return False # no success

            write(data)
            size -= data_len

        self._fout.flush()

        return bool(self._read_num()) # success?
