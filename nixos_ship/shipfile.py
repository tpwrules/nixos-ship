import zipfile

class ShipfileWriter:
    def __init__(self, workdir, path):
        self.workdir = workdir
        self.workdir.mkdir(parents=True)

        self.zip = zipfile.ZipFile(path, mode="w")

    def close():
        self.zip.close()

    def open_store_paths_file(self):
        f = self.zip.open("nixos-ship-data/store_paths.nar",
            "w", force_zip64=True)

        return f

    def open_path_info_file(self):
        f = self.zip.open("nixos-ship-data/path_info.json", "w")

        return f

class ShipfileReader:
    def __init__(self, workdir, path):
        self.workdir = workdir
        self.workdir.mkdir(parents=True)

        self.zip = zipfile.ZipFile(path, mode="r")

    def close():
        self.zip.close()

    def open_store_paths_file(self):
        f = self.zip.open("nixos-ship-data/store_paths.nar", "r")

        return f

    def open_path_info_file(self):
        f = self.zip.open("nixos-ship-data/path_info.json", "r")

        return f
