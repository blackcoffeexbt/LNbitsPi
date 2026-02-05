{ pkgs }:

pkgs.python3Packages.buildPythonApplication {
  pname = "lnbitspi-configurator";
  version = "1.0.0";

  src = ./configurator-app;

  # Python dependencies
  propagatedBuildInputs = with pkgs.python3Packages; [
    flask
    mnemonic  # BIP39 mnemonic generation
  ];

  # Don't run tests (we don't have any)
  doCheck = false;

  # Install phase: copy application files
  installPhase = ''
    runHook preInstall

    mkdir -p $out/lib/lnbitspi-configurator
    mkdir -p $out/bin

    # Copy application files
    cp -r ${./configurator-app}/* $out/lib/lnbitspi-configurator/

    # Create wrapper script
    cat > $out/bin/lnbitspi-configurator << 'EOF'
#!/usr/bin/env bash
set -euo pipefail

cd $out/lib/lnbitspi-configurator
exec ${pkgs.python3}/bin/python app.py "$@"
EOF

    chmod +x $out/bin/lnbitspi-configurator

    runHook postInstall
  '';

  meta = with pkgs.lib; {
    description = "LNbitsPi first-run configuration wizard";
    license = licenses.mit;
    platforms = platforms.linux;
  };
}
