{
  description = "NixOS Raspberry Pi 4 SD image running LNbits";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.11";

    # Raspberry Pi firmware + SD image module
    # Using main branch for better cache coverage
    raspberry-pi-nix.url = "github:nix-community/raspberry-pi-nix";
    raspberry-pi-nix.inputs.nixpkgs.follows = "nixpkgs";

    # LNbits flake input (you can pin to a tag/commit later)
    lnbits.url = "github:lnbits/lnbits";
  };

  outputs = { self, nixpkgs, raspberry-pi-nix, lnbits, ... }:
  let
    system = "aarch64-linux";
  in
  {
    nixosConfigurations.pi4 = nixpkgs.lib.nixosSystem {
      inherit system;
      specialArgs = { inherit lnbits; };
      modules = [
        raspberry-pi-nix.nixosModules.raspberry-pi
        ./nixos/configuration.nix
      ];
    };
  };
}