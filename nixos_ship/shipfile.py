import zipfile
import zstandard

class ShipfileWriter:
    def __init__(self, workdir, path):
        self.workdir = workdir
        self.workdir.mkdir(parents=True)

        self.zip = zipfile.ZipFile(path, mode="w")

    def close(self):
        self.zip.close()

    def open_store_paths_file(self, compression="normal"):
        f = self.zip.open("nixos-ship-data/store_paths.bin.zst",
            "w", force_zip64=True)

        if compression == "ultra":
            params = zstandard.ZstdCompressionParameters.from_level(22,
                enable_ldm=True, window_log=31, threads=-1)
        elif compression == "normal":
            params = zstandard.ZstdCompressionParameters.from_level(9,
                enable_ldm=True, window_log=31, threads=-1)
        elif compression == "fast":
            params = zstandard.ZstdCompressionParameters.from_level(3,
                threads=-1)

        compressor = zstandard.ZstdCompressor(compression_params=params)
        writer = compressor.stream_writer(f)

        return writer

    def open_path_info_file(self):
        f = self.zip.open("nixos-ship-data/path_info.json.zst", "w")

        compressor = zstandard.ZstdCompressor(level=22)
        writer = compressor.stream_writer(f)

        return writer

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
