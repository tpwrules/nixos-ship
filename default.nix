{ pkgs ? import <nixpkgs> { }
}:

with pkgs;
python3.pkgs.buildPythonApplication rec {
  name = "nixos-ship";
  src = ./.;
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
