import io
import tarfile
import json

import zstandard

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

class ShipfileWriter:
    def __init__(self, workdir, path, compression="normal"):
        self.workdir = workdir
        self.workdir.mkdir(parents=True)

        compressor = get_compressor(compression)
        self._file = open(path, mode="wb")
        self._writer = compressor.stream_writer(self._file)
        # 128K buf size picked because that's what the zstandard library
        # uses as its default buffer sizes
        self.tar = tarfile.open(fileobj=self._writer, mode="w|",
            format=tarfile.PAX_FORMAT, copybufsize=131072)

    def close(self):
        self.tar.close()
        self._writer.close()
        self._file.close()

    def write_version_info(self, mandatory_features=[], optional_features=[]):
        contents = dump_json({
            "mandatory_features": mandatory_features,
            "optional_features": optional_features,
            "version": 1,
        })

        info = tarfile.TarInfo("shipfile/metadata/version_info.json")
        info.type = tarfile.REGTYPE # regular file
        info.size = len(contents)

        self.tar.addfile(info, io.BytesIO(contents))

    def write_config_info(self, config_paths):
        contents = dump_json(
            {str(k): {"path": str(v)} for k, v in config_paths.items()})

        info = tarfile.TarInfo("shipfile/metadata/config_info.json")
        info.type = tarfile.REGTYPE # regular file
        info.size = len(contents)

        self.tar.addfile(info, io.BytesIO(contents))

    def write_store_info(self):
        contents = b"StoreDir: /nix/store\n"

        info = tarfile.TarInfo("shipfile/store/nix-cache-info")
        info.type = tarfile.REGTYPE # regular file
        info.size = len(contents)

        self.tar.addfile(info, io.BytesIO(contents))

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
        info = tarfile.TarInfo(f"shipfile/store/{p}.narinfo")
        info.type = tarfile.REGTYPE # regular file
        info.size = len(contents)

        self.tar.addfile(info, io.BytesIO(contents))

    def write_nar(self, nar_hash, nar_size, fp):
        info = tarfile.TarInfo(f"shipfile/store/nar/{nar_hash}.nar")
        info.type = tarfile.REGTYPE # regular file
        info.size = nar_size

        self.tar.addfile(info, fp)

class ShipfileReader:
    def __init__(self, workdir, path):
        self.workdir = workdir
        self.workdir.mkdir(parents=True)

        self.zip = zipfile.ZipFile(path, mode="r")

    def close(self):
        self.zip.close()

    def open_store_paths_file(self):
        f = self.zip.open("nixos-ship-data/store_paths.bin.zst", "r")

        # set max window size to accommodate the large window modes
        decompressor = zstandard.ZstdDecompressor(max_window_size=2**31)
        reader = decompressor.stream_reader(f)

        return reader

    def open_path_info_file(self):
        f = self.zip.open("nixos-ship-data/path_info.json.zst", "r")

        decompressor = zstandard.ZstdDecompressor()
        reader = decompressor.stream_reader(f)

        return reader
