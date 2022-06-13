{
  description = "nixos-ship";

  inputs.flake-utils.url = "github:numtide/flake-utils";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-22.05";

  outputs = { self, nixpkgs, flake-utils }:
    nixpkgs.lib.foldr nixpkgs.lib.recursiveUpdate { } [
      (flake-utils.lib.eachDefaultSystem (system: {
        packages.nixos-ship = (import ./. {
          pkgs = nixpkgs.legacyPackages.${system};
        });

        defaultPackage = self.packages.${system}.nixos-ship;
      }))
    ];
}
