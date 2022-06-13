import zipfile
import zstandard

class ShipfileWriter:
    def __init__(self, workdir, path):
        self.workdir = workdir
        self.workdir.mkdir(parents=True)

        self.zip = zipfile.ZipFile(path, mode="w")

    def close(self):
        self.zip.close()

    def open_store_paths_file(self):
        f = self.zip.open("nixos-ship-data/store_paths.bin.zst",
            "w", force_zip64=True)

        compressor = zstandard.ZstdCompressor(level=9, threads=-1)
        writer = compressor.stream_writer(f)

        return writer

    def open_path_info_file(self):
        f = self.zip.open("nixos-ship-data/path_info.json", "w")

        return f

class ShipfileReader:
    def __init__(self, workdir, path):
        self.workdir = workdir
        self.workdir.mkdir(parents=True)

        self.zip = zipfile.ZipFile(path, mode="r")

    def close(self):
        self.zip.close()

    def open_store_paths_file(self):
        f = self.zip.open("nixos-ship-data/store_paths.bin.zst", "r")

        compressor = zstandard.ZstdDecompressor()
        reader = compressor.stream_reader(f)

        return reader

    def open_path_info_file(self):
        f = self.zip.open("nixos-ship-data/path_info.json", "r")

        return f
