{ pkgs ? import <nixpkgs> { }
}:

with pkgs;
python3.pkgs.buildPythonApplication rec {
  pname = "nixos-ship";
  version = "0.3.1";

  src = ./nixos_ship;
  buildInputs = [ makeWrapper ];
  propagatedBuildInputs = [ python3.pkgs.zstandard ];

  pythonImportsCheck = ["nixos_ship"];

  makeWrapperArgs =
    let
      binPath = [ pkgs.nixVersions.stable or nix_2_4 git ];
    in
    [
      "--prefix PATH : ${lib.makeBinPath binPath}"
      "--set NIX_SSL_CERT_FILE ${cacert}/etc/ssl/certs/ca-bundle.crt"
    ];
}
