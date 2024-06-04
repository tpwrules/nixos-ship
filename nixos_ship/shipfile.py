import io
import tarfile
import json
import sys

import zstandard

from .nix_store import PathInfo

def get_compressor(compression):
    if compression == "ultra":
        params = zstandard.ZstdCompressionParameters.from_level(22,
            enable_ldm=True, window_log=31, threads=-1)
    elif compression == "normal":
        params = zstandard.ZstdCompressionParameters.from_level(9,
            enable_ldm=True, window_log=31, threads=-1)
    elif compression == "fast":
        params = zstandard.ZstdCompressionParameters.from_level(3,
            threads=-1)

    return zstandard.ZstdCompressor(compression_params=params)

def dump_json(obj):
    # dump an object as json with reproducible settings
    dumped = json.dumps(obj,indent=2, sort_keys=True, ensure_ascii=False)
    return dumped.encode("utf8")

def parse_nix_kv(contents):
    # parse a Nix-style Key: value file

    pairs = contents.split("\n")
    # if the file ended with a newline, the last pair will be empty
    if len(pairs) > 0 and pairs[-1].strip() == "":
        pairs.pop()
    
    parsed = {}
    for pair in pairs:
        key, value = (c.strip() for c in pair.split(":", maxsplit=1))

        # for some cursed reason, keys can be duplicated. turn duplicated keys
        # into a list of their values.
        if key in parsed:
            lv = parsed[key]
            if isinstance(lv, list):
                lv.append(value)
            else:
                parsed[key] = [lv, value]
        else:
            parsed[key] = value

    return parsed

# something went wrong parsing a shipfile
class ShipfileError(RuntimeError):
    pass

# maximum expected size of anything which is not a .nar file
MAX_METADATA_SIZE = 1048576

class SplitWriter:
    def __init__(self, path, split_size):
        self._path = str(path)
        self._split_size = split_size

        # eagerly open file in case there's a problem
        self._file = open(self._path, "wb")
        self._file_number = 0
        self._curr_size = 0

    def write(self, data):
        total_len = len(data)
        while len(data) > 0:
            data_len = len(data)
            amount = min(data_len, self._split_size-self._curr_size)
            if amount == data_len: # still enough space, just write it
                self._file.write(data)
                self._curr_size += data_len
                return total_len
            else: # write the part that fits
                self._file.write(data[:amount])
                data = data[amount:] # save the rest for next time
                # move to next file
                self._file.close()
                self._file_number += 1
                self._file = open(self._path+"."+str(self._file_number), "wb")
                self._curr_size = 0

        return total_len

    def close(self):
        return self._file.close()

class ShipfileWriter:
    def __init__(self, workdir, path, compression="normal", split_size=None):
        self.workdir = workdir
        self.workdir.mkdir(parents=True)

        compressor = get_compressor(compression)
        self._is_split = split_size is not None
        if self._is_split:
            self._file = SplitWriter(path, split_size)
        else:
            self._file = open(path, "wb")
        self._writer = compressor.stream_writer(self._file)
        self._tar = tarfile.open(fileobj=self._writer, mode="w:",
            format=tarfile.PAX_FORMAT)

    def close(self):
        self._tar.close()
        self._writer.close()
        self._file.close()

    def _write_fp(self, path, size, fp):
        info = tarfile.TarInfo(path)
        info.type = tarfile.REGTYPE # regular file
        info.size = size

        self._tar.addfile(info, fp)

    def _write_contents(self, path, contents):
        self._write_fp(path, len(contents), io.BytesIO(contents))

    def write_version_info(self, mandatory_features=[], optional_features=[]):
        if self._is_split:
            mandatory_features.append("simple_split")

        contents = dump_json({
            "mandatory_features": sorted(mandatory_features),
            "optional_features": sorted(optional_features),
            "version": 1,
        })

        self._write_contents("shipfile/metadata/version_info.json", contents)

    def write_config_info(self, config_paths):
        contents = dump_json(
            {str(k): {"path": str(v)} for k, v in config_paths.items()})

        self._write_contents("shipfile/metadata/config_info.json", contents)

    def write_store_info(self):
        contents = b"StoreDir: /nix/store\n"

        self._write_contents("shipfile/store/nix-cache-info", contents)

    def write_narinfo(self, path_info, in_file):
        url = ""
        if in_file:
            url = f"nar/{path_info.nar_hash.split(':')[1]}.nar"

        refs = " ".join(r.replace("/nix/store/", "")
            for r in path_info.references)

        deriver = path_info.deriver.replace("/nix/store/", "")

        contents = (
            f"StorePath: {path_info.path}\n"
            +(f"URL: {url}\n")
            +"Compression: none\n"
            +f"FileHash: {path_info.nar_hash}\n"
            +f"FileSize: {path_info.nar_size}\n"
            +f"NarHash: {path_info.nar_hash}\n"
            +f"NarSize: {path_info.nar_size}\n"
            +f"References: {refs}\n"
            +(f"Deriver: {deriver}\n" if deriver != "" else "")
            +("".join(f"Sig: {s}\n" for s in path_info.sigs))
            +(f"CA: {path_info.ca_info}\n" if path_info.ca_info != "" else "")
        ).encode("ascii")

        p = path_info.path.replace("/nix/store/", "").split("-")[0]
        self._write_contents(f"shipfile/store/{p}.narinfo", contents)

    def sink_nar_into(self, nar_hash, nar_size, fp):
        # write a nar into the shipfile, taking an fp to get the nar data from

        self._write_fp(f"shipfile/store/nar/{nar_hash.split(':')[1]}.nar",
            nar_size, fp)

class ShipfileReader:
    def __init__(self, workdir, path):
        self.workdir = workdir
        self.workdir.mkdir(parents=True)

        # set max window size to accommodate the large window modes from the
        # shipfile sender
        decompressor = zstandard.ZstdDecompressor(max_window_size=2**31)
        self._file = open(path, mode="rb")
        self._reader = decompressor.stream_reader(self._file)
        self._tar = tarfile.open(fileobj=self._reader, mode="r:")

        self._state = "initial"
        self._ungot_entry = None

    def close(self):
        self._tar.close()
        self._reader.close()
        self._file.close()

    def _next_entry(self):
        # return the next entry from the tarfile

        if self._ungot_entry is not None:
            entry = self._ungot_entry
            self._ungot_entry = None
            return entry

        while True:
            entry = self._tar.next()
            if entry is None: # the file is over
                return None
            # we only want file entries
            if entry.type == tarfile.REGTYPE:
                break

        return entry

    def _unget_entry(self, entry):
        # take an entry and return it from _next_entry next time

        if self._ungot_entry is not None:
            raise RuntimeError(f"entry {self._ungot_entry} was already ungot")

        self._ungot_entry = entry

    def check_version_info(self):
        # read the version info from a shipfile and check that the features
        # it needs are compatible with what we know about

        if self._state != "initial":
            raise RuntimeError(f"invalid state {self._state} for version check")

        entry = self._next_entry()
        if entry is None:
            raise ShipfileError("shipfile is empty")

        if entry.name != "shipfile/metadata/version_info.json":
            raise ShipfileError("shipfile starts with incorrect entry "
                f"{entry.name}")

        contents = self._tar.extractfile(entry).read(entry.size).decode("utf8")
        version_info = json.loads(contents)

        # very first check in case something changes drastically
        self._version = version_info.get("version")
        if self._version != 1:
            raise ShipfileError(f"unknown version {self._version}")

        try:
            self._mandatory_features = set(version_info["mandatory_features"])
            self._optional_features = set(version_info["optional_features"])
        except KeyError:
            raise ShipfileError("missing keys in version_info.json")

        if len(self._mandatory_features) > 0:
            raise ShipfileError("unknown mandatory features "
                f"{self._mandatory_features}")
        
        if len(self._optional_features) > 0:
            print("WARNING: unknown optional features "
                f"{self._optional_features}", file=sys.stderr)

        if len(version_info) > 3:
            raise ShipfileError("unexpected keys in version_info.json")

        self._state = "metadata"

    def read_metadata(self):
        # read and parse everything in the metadata/ folder

        if self._state != "metadata":
            raise RuntimeError(f"invalid state {self._state} for metadata read")

        while True:
            entry = self._next_entry()
            if entry is None:
                break
            if not entry.name.startswith("shipfile/metadata/"):
                self._unget_entry(entry)
                break

            if entry.name == "shipfile/metadata/config_info.json":
                self.config_info = self._read_config_info(entry)

        if self.config_info is None:
            raise ShipfileError("config_info.json is missing")

        self._state = "store_metadata"

    def read_store_metadata(self):
        # read and parse everything in the store/ folder (except .nar files)

        if self._state != "store_metadata":
            raise RuntimeError(f"invalid state {self._state} for "
                "store metadata read")

        self.path_infos = []
        self.path_list = []
        while True:
            entry = self._next_entry()
            if entry is None:
                break

            if (not entry.name.startswith("shipfile/store/")) or \
                    entry.name.startswith("shipfile/store/nar/"):
                self._unget_entry(entry)
                break

            if entry.name == "shipfile/store/nix-cache-info":
                self.cache_info = self._read_cache_info(entry)
            elif entry.name.endswith(".narinfo"):
                path_info, in_file = self._read_narinfo(entry)
                self.path_infos.append(path_info)
                if in_file:
                    self.path_list.append(path_info.path)

        if self.cache_info is None:
            raise ShipfileError("nix-cache-info is missing")

        self._state = "read_nar"

    def _read_config_info(self, entry):
        contents = self._tar.extractfile(entry).read(entry.size).decode("utf8")
        config_info = json.loads(contents)

        # remove indirection of path key
        return {k: v["path"] for k, v in config_info.items()}

    def _read_cache_info(self, entry):
        contents = self._tar.extractfile(entry).read(entry.size).decode("utf8")
        cache_info = parse_nix_kv(contents)

        if cache_info["StoreDir"] != "/nix/store":
            raise ShipfileError("sorry, we don't pretend to support not "
                "/nix/store yet!")

        return cache_info

    def _read_narinfo(self, entry):
        contents = self._tar.extractfile(entry).read(entry.size).decode("utf8")
        narinfo = parse_nix_kv(contents)

        if narinfo["Compression"] != "none" or \
                narinfo["FileSize"] != narinfo["NarSize"] or \
                narinfo["FileHash"] != narinfo["NarHash"]:
            raise ShipfileError("invalid compression situation")

        in_file = narinfo["URL"] != ""
        refs = ["/nix/store/"+r.strip() for r in narinfo["References"].split()]
        deriver = narinfo.get("Deriver", "")
        if deriver != "":
            deriver = "/nix/store/"+deriver
        sigs = narinfo.get("Sig", [])
        if not isinstance(sigs, list):
            sigs = [sigs]
        ca_info = narinfo.get("CA", "")

        path_info = PathInfo(path=narinfo["StorePath"],
            deriver=deriver,
            references=refs,
            nar_size=int(narinfo["NarSize"]),
            nar_hash=narinfo["NarHash"],
            ca_info=ca_info,
            sigs=sigs
        )

        return path_info, in_file

    def source_nar_into(self, nar_hash, nar_sink_fn):
        # read a nar from the shipfile, taking a function which is provided the
        # fp and that reads the nar data out of it

        path = f"shipfile/store/nar/{nar_hash.split(':')[1]}.nar"
        while True:
            entry = self._next_entry()
            if entry is None:
                raise ShipfileError(f"could not find nar {path}")
            if entry.name == path:
                break

        nar_sink_fn(self._tar.extractfile(entry))
