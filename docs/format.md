# Shipfile Format

The shipfile format is, at its core, a Zstd-compressed pax archive with
extension `.shf`. The members within the archive are fully defined and ordered
in reference to this documentation. The archive must not contain any members
(files, directories, or otherwise) not explicitly listed here, with the
exception of pax extended headers. Unexpected members are ignored for future
compatibility. Directory members are never explicitly written into the
archive.

## Shipfile Folders

The archive contains a single folder called `shipfile/` which contains all its
data. This root folder contains two folders to separate the two types of
data. These folders are listed below in the order they must appear in the
archive.

1. `metadata/`: All information describing the shipfile.
2. `store/`: Data on store paths and store objects contained in the shipfile.

### Shipfile Metadata Folder

The folder `shipfile/metadata/` contains all information describing the
shipfile. It contains the following files. These files are listed in the order
they must appear in the archive.

1. `version_info.json`: UTF-8-encoded JSON containing information on
    interpreting the shipfile. Must be the very first member in the archive.
2. `config_info.json`: UTF-8-encoded JSON containing information specific to
    each NixOS config within the shipfile.

#### Version Info File

The file `shipfile/metadata/version_info.json` contains a JSON object which
describes the version of the shipfile and what must be understood by the
receiver to correctly interpret it. This must be the very first member in the
archive (pax extended headers excepted); it is an error if it is not.

The root object contains three keys, listed below. It is an error if other keys
are found.

1. `mandatory_features`: List of strings describing features which the receiver
    must understand to correctly use this shipfile. If an unknown feature is
    listed here, the shipfile is rejected.
2. `optional_features`: List of strings describing features which the receiver
    may be interested in, but are not required. If an unknown feature is listed
    here, the user is warned but the shipfile is accepted.
3. `version`: Integer describing the overall version of the shipfile. If not
    known by the receiver, the shipfile is rejected.

No features of either type are currently defined. The shipfile version is
currently 1.

Note that the JSON should be sorted lexicographically by keys and pretty-printed
with 2 spaces of indentation for reproducibility.

An example version info file is presented below.

```
{
  "mandatory_features": [],
  "optional_features": [],
  "version": 1
}
```

#### Config Info File

The file `shipfile/metadata/config_info.json` contains a JSON object which
describes each NixOS config in the shipfile. The root object maps config names
(which are conventionally machine hostnames, and the attributes of the
originating flake's `nixosConfigurations`) to an object containing information
on the particular config.

Each config object has a `path` key which contains the full store path of that
particular configuration. Other keys are ignored for future compatibility.

Note that the JSON should be sorted lexicographically by keys and pretty-printed
with 2 spaces of indentation for reproducibility. 

An example config info file is presented below.

```
{
  "config1": {
    "path": "/nix/store/jd1fm7a0x5g95cy2bjemfwy0nxg74zmz-nixos-system-config1-22.05.20220614.9ff91ce"
  },
  "config2": {
    "path": "/nix/store/fqvs5xlbkf7np3f3snrfddpcpa815vk9-nixos-system-config2-22.05.20220614.9ff91ce"
  }
}
```

### Store Folder

The folder `shipfile/store/` contains a Nix binary cache inspired representation
of the store paths and objects in the shipfile. The representation is intended
to be largely compatible for interoperability and future use of the format.

This folder contains the following groups of files. These file groups are listed
in the order they must appear in the archive. Each group of files is sorted as
described with that particular group.

1. `nix-cache-info`: Contains metadata on the store.
2. `*.narinfo`: Contains .narinfo files for the closure of all paths referenced
    in the shipfile.
3. `nar/*.nar`: Containes uncompressed .nar files for all paths actually in this
    store, which may be fewer than above due to delta creation.

#### Store Metadata

The file `shipfile/store/nix-cache-info` contains the Nix binary cache store
metadata in `Key: value` format. Currently, this has just one key: the
directory the store is contained in, whose value is expected to be
`/nix/store`. Additional keys are ignored for future compatibility.

Store paths are specific to the store directory, so you cannot ship systems
built by a Nix with one store directory to a Nix with another. That is not a
big concern because the majority of Nix installs do use `/nix/store` as the
store directory, and bear in mind the `nixos-ship` program itself hasn't really
been tested with any other.

An example metadata file is presented below.

```
StoreDir: /nix/store
```

#### .narinfo Files

The group of files `shipfile/store/*.narinfo` contain metadata for all paths
referenced in the store in `Key: value` format. These files are sorted
topologically as described in the section at the end of this document.

Each `.narinfo` file describes the store path whose hash is contained in its
name. There is a `.narinfo` file for each path in the closure of all paths
referenced in the shipfile's metadata, e.g. for each configuration listed in
`shipfile/metadata/config_info.json`.

The `.narinfo` file has the following keys in the following order. The reference
for the `.narinfo` format is taken to be the
[Nix source code](https://github.com/NixOS/nix/blob/561a258f1d9fd11a5e111e14c492ee166a7551c1/src/libstore/nar-info.cc).
Additional keys are ignored for future compatibility.

1. `StorePath`: The complete store path described by this `.narinfo`.
2. `URL`: The relative path to the `.nar` containing the contents of the
    store path, usually `nar/<FileHash>.nar`. May be the same in multiple
    `.narinfo` files (though note that this does refer to two separate but
    identical files!). May be blank if the `.nar` has been omitted from the
    shipfile.
3. `Compression`: The type of compression employed by the `.nar`. Must be `none`
    within a shipfile.
4. `FileHash`: The compressed hash of the `.nar`. Must be `sha256` within a
    shipfile.
5. `FileSize`: The compressed size in bytes of the `.nar`.
6. `NarHash`: The uncompressed hash of the `.nar`. Must be `sha256` within a
    shipfile. As compression is disallowed, this must be the same as `FileHash`.
7. `NarSize`: The uncompressed size of the `.nar`. As compression is disallowed,
    this must be the same as `FileSize`.
8. `References`: Zero or more space-separated store path names that this path
    references. Must always be present even if empty. Path names are sorted
    as described in the section at the end of this document.
9. `Deriver`: The store path name of the derivation which resulted in this store
    path. May not be present.
10. `Sig`: Information on the signature of this store path. This key may be
    present zero or more times. Key instances are sorted lexicographically. This
    key's contents are treated as opaque by the format.
11. `CA:` Information relating to content-addressed derivations. May not be
    present. This key's contents are treated as opaque by the format.

An example `.narinfo` file is presented below. This file would be named
`shipfile/store/xbqj64vdr3z13nlf8cvl1lf5lxa16mha.narinfo`.

```
StorePath: /nix/store/xbqj64vdr3z13nlf8cvl1lf5lxa16mha-hello-2.12.1
URL: nar/11w4fdahp53jgzwlckl3digjpcyv1f353m96h81sbl1q0n79biv6.nar
Compression: none
FileHash: sha256:11w4fdahp53jgzwlckl3digjpcyv1f353m96h81sbl1q0n79biv6
FileSize: 129960
NarHash: sha256:11w4fdahp53jgzwlckl3digjpcyv1f353m96h81sbl1q0n79biv6
NarSize: 129960
References: y5cp9q9h6p80mzbsijs00zxpi7g0lc9d-apple-framework-CoreFoundation-11.0.0
Deriver: jmhnhycq16nd28lz7iparknw7791l0fg-hello-2.12.1.drv
Sig: cache.nixos.org-1:fx4eIoWGPkisIGEEM9+CDbZcJ6WpMbhlGn0LEEGkjfZZnt8+lut045/4eO++MairDfLAn+kFHCjs0LrNEXhLAw==
```

#### .nar files

The group of files `shipfile/store/nar/*.nar` contains the actual data for the
paths contained within the shipfile. Not all paths will be contained as some
will be assumed to already be on the target system in delta compression mode.
The `.nar` files must be ordered the same as the `.narinfo` files which
reference each. These must be the very last members in the archive; it is an
error if they are not.

Because `.nar` files are identified by the hash of their contents, and there
must be one `.nar` file per `.narinfo` file for sorting and streaming purposes,
the files may end up duplicated in the archive. This is something to be aware
of, but overall a minor concern because the pax format allows for this,
duplicate `.nar` files must by definition have identical contents, and the
compression will likely notice and deduplicate them unless they are very large.

The `.nar` format is defined by Figure 5.2 on page 101 of the
[Nix thesis](https://edolstra.github.io/pubs/phd-thesis.pdf), but is treated as
opaque by the format.

## Other Issues

### Philosophy

This format was designed according to four criteria, listed below in no
particular order. It's not guaranteed to follow them absolutely, but it
definitely hopes to try.

* Reproducibility: Given the same version of `nixos-ship` (and dependencies)
    and the same input command, the same shipfile will be produced, down to
    the last bit. This is achieved by rigorously specifying the contents of
    the shipfile and their ordering.
* Economy: The format shall not be wasteful of space or time. This is achieved
    by using modern fast compression and decompression algorithms (Zstd),
    careful ordering of the shipfile contents, and the delta compression mode.
* Inspectability: The format shall be easily unpackable with standard tools and,
    in a pinch, manually installable as well. This is achieved by using
    well-known file formats (Zstd and pax), human-readable metadata formats, and
    ultimately being a repacking of the binary cache format already understood
    by Nix.
* Extensibility: The format shall be logically extensible to future enhancements
    and compatible with older receivers. This is achieved by encoding version
    information and dividing the contents into logically separate parts.

### Sorting

Proper sorting of archive members and file contents is essential for
reproducibility. The order of all archive members is specified in the
description of the format above. Here, we define the three types of sorting
used for some parts of the archive and within particular files.

#### Lexicographical Sorting
    
This operation sorts strings by comparing each character's Unicode codepoint in
order. Numerically lesser codepoints sort before numerically greater
codepoints, and shorter strings sort before longer strings.

This sorting is used by, for example, JSON keys and the `Sig` fields in .narinfo
files.

#### Path Sorting

Nix store paths are sorted first by the name component (i.e. the part past the
first `-` after the hash), then by the hash. Each component is sorted
lexicographically as defined above.

For example, the following three paths:
```
/nix/store/cn6w2xc0hfs22iv9ps54nnm6p7qidg0j-db-4.8.30
/nix/store/gh7k6psd3xawrfdvgnan3cirgq2xbfq1-audit-2.8.5
/nix/store/d0iwnlr30ykqm5ynm0bbk6bsjjc750ad-bash-5.1-p16
```

are sorted as:
```
/nix/store/gh7k6psd3xawrfdvgnan3cirgq2xbfq1-audit-2.8.5
/nix/store/d0iwnlr30ykqm5ynm0bbk6bsjjc750ad-bash-5.1-p16
/nix/store/cn6w2xc0hfs22iv9ps54nnm6p7qidg0j-db-4.8.30
```

This improves compression as store paths with similar names are more likely to
have similar contents, so they will be placed closer together in the final
archive, allowing the compression algorithm to see their similarities.

This sorting is used by, for example, the `References` field in .narinfo files.

#### Topological Sorting

The actual `.narinfo` files, and thus `.nar` files, are sorted topologically.
That is, for a particular `.narinfo` file, the `.narinfo` files for all the
store paths its `References` field contains must already have been written out
into the archive before that file.

Before topological sorting, the paths are sorted as defined above. Note that
some topological sorting algorithms can produce different output for the same
input; these must not be used. Certain algorithms also more closely preserve
the input ordering which is advantageous for compression as described above.

Topological sorting is necessary so that the `.nar` files can be streamed from
the archive into the store. Nix does not allow a store object to be imported if
any paths it references are not already in the store. Topological sorting in
this manner ensures this constraint will not be violated if objects are
imported in archive order.

### Content-Addressed Derivations

Content-addressed derivations are an upcoming Nix feature whereby, instead of
most derivations naming their output paths by the hash of their input data, the
output paths are named by their contents. This requires a separate mapping of
derivations to output paths so that Nix knows when a particular derivation's
output already exists. This information is currently stored in
`realisations/*.doi` files in the Nix binary cache format.

However, the Nix tooling is not yet mature enough to enshrine this behavior in
this specification, or even reliably extract the relevant information. CA paths
are shipped correctly by `nixos-ship` and will be accepted by the shipped-to
store, but the database will not receive the realisation information. This means
that if the source derivation is realised on the shipped-to machine, Nix will
be unable to recognize that its result already exists and will rebuild it.

This limitation will be addressed in a future update as content-addressed
tooling matures and usage increases.
