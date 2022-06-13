from enum import IntEnum
from dataclasses import dataclass, asdict
from typing import Optional
import subprocess
import struct

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

class LocalStore:
    def __init_(self):
        self._proc = None

    def __enter__(self):
        self._proc = subprocess.Popen([
            "nix-store", "--serve", "--write"
        ], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        
        c = None
        try:
            c = StoreCommunicator(self._proc.stdout, self._proc.stdin)
        finally:
            if c is None:
                self._close()

        return c

    def _close(self):
        self._proc.stdin.close()
        self._proc.stdout.close()
        self._proc.wait()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._close()

class StoreCommunicator:
    def __init__(self, fin, fout):
        self._fin = fin
        self._fout = fout
        self._buf = memoryview(bytearray(131072))

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
        return struct.unpack("<Q", self._fin.read(8))[0]

    def _write_num(self, num):
        self._fout.write(struct.pack("<Q", num))

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

    def dump_nar_into(self, path, size, file):
        self._write_num(ServeCommand.DUMP_STORE_PATH)
        self._write_string(path)
        self._fout.flush()

        while size > 0:
            num_read = self._fin.readinto(self._buf[:min(size, len(self._buf))])
            if num_read == 0:
                break

            file.write(self._buf[:num_read])
            size -= num_read

    def add_nar_from(self, path_info, file):
        self._write_num(ServeCommand.ADD_TO_STORE_NAR)
        self._write_string(path_info.path)
        self._write_string(path_info.deriver)
        self._write_string(path_info.nar_hash)
        self._write_strings(path_info.references)
        self._write_num(0) # registrationTime
        self._write_num(path_info.nar_size)
        self._write_num(0) # ultimate: did we actually build this nar?
        self._write_strings(path_info.sigs)
        self._write_strings(path_info.ca_info)

        size = path_info.nar_size
        while size > 0:
            num_read = file.readinto(self._buf[:min(size, len(self._buf))])
            if num_read == 0:
                break

            self._fout.write(self._buf[:num_read])
            size -= num_read

        self._fout.flush()

        return bool(self._read_num()) # success?
