{ config, pkgs, ... }:

let
  adminPkg = pkgs.callPackage ./admin-package.nix { };
in
{
  systemd.services.lnbitspi-admin = {
    description = "LNbitsBox admin dashboard";
    after = [ "network-online.target" ];
    wants = [ "network-online.target" ];
    wantedBy = [ "multi-user.target" ];

    # Only run after system is configured
    unitConfig = {
      ConditionPathExists = "/var/lib/lnbits/.configured";
    };

    # systemctl must be in PATH for service restart/shutdown commands
    path = [ pkgs.systemd pkgs.wpa_supplicant pkgs.iw ];

    serviceConfig = {
      Type = "simple";
      # Runs as root for /etc/shadow access (PAM auth) and systemctl
      User = "root";
      Group = "root";

      ExecStart = "${adminPkg}/bin/lnbitspi-admin";

      Restart = "on-failure";
      RestartSec = 5;

      PrivateTmp = true;
    };
  };
}
