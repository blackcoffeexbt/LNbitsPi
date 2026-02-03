# LNbits NixOS Raspberry Pi 4 image

This repo builds a flashable NixOS SD-card image for Raspberry Pi 4 that runs LNbits as a systemd service.

## Download and flash

1. Go to **Releases** and download the latest `*.img.zst` and `SHA256SUMS.txt`
2. Flash the image to an SD card:
   - Raspberry Pi Imager (recommended), or
   - `zstd -d` then `dd` on Linux/macOS

Example on Linux/macOS (be careful with the disk name):

```bash
zstd -d lnbits-nixos-pi4-*.img.zst -o image.img
sudo dd if=image.img of=/dev/rdiskX bs=8m conv=sync status=progress
```

# To build the image yourself, see below for instructions on how to do this on Debian/Ubuntu.

## **0) Prep the Debian VM**

  

Update and install basics:

```
sudo apt update
sudo apt install -y curl git xz-utils zstd ca-certificates
```

You’ll want at least **20–30 GB free disk** and ideally **4–8 GB RAM** (or add swap).

  

Optional but often helpful: add swap (8GB example)

```
sudo fallocate -l 8G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```


## **1) Install Nix (multi-user) and enable flakes**


Use the same install you pasted (good for Debian):

```bash
sh <(curl --proto '=https' --tlsv1.2 -L https://nixos.org/nix/install) --daemon --yes
```

Enable nix-command and flakes:

```bash
grep -qxF 'experimental-features = nix-command flakes' /etc/nix/nix.conf || \
echo 'experimental-features = nix-command flakes' | sudo tee -a /etc/nix/nix.conf
```

Restart daemon:

```bash
sudo systemctl restart nix-daemon
```

Load Nix profile into your shell (needed in fresh shells):

```bash
. /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh
```

(If you want it permanent, add that line to ~/.bashrc.)


## **2) Enable building aarch64 on x86 (QEMU/binfmt)**

Install QEMU user emulation + binfmt support:

```bash
sudo apt install -y qemu-user-static binfmt-support
```

Now enable aarch64 in Nix config so it will attempt cross/emulated builds:

```bash
grep -qxF 'extra-platforms = aarch64-linux' /etc/nix/nix.conf || \
echo 'extra-platforms = aarch64-linux' | sudo tee -a /etc/nix/nix.conf

sudo systemctl restart nix-daemon
```

Sanity check:

```bash
nix show-config | grep extra-platforms
```

You should see aarch64-linux listed.

## **3) Clone your repo and build the SD image**

Clone:

```bash
git clone https://github.com/blackcoffeexbt/lnbitspi
cd lnbitspi
```

If you committed flake.lock, keep it. If not, generate it (recommended):

```bash
nix flake lock
```

Build the SD image:

```bash
nix build .#nixosConfigurations.pi4.config.system.build.sdImage -L
```

Result will appear at something like:

```bash
ls -lah result/sd-image/
```

You should see a *.img.zst.


Copy it somewhere convenient:

```bash
mkdir -p dist
cp -v result/sd-image/*.img.zst dist/
sha256sum dist/*.img.zst > dist/SHA256SUMS.txt
```

## **4) Test the output file is a proper image**

```bash
file dist/*.img.zst
zstd -t dist/*.img.zst
```

## ## **5) Flash to SD
Flash using Raspberry Pi Imager (recommended) or `zstd -d` + `dd` on Linux/macOS.

# If build is slow
Building on x86 with QEMU emulation can be slow. If you have access to an aarch64 machine (like a Raspberry Pi 4 running NixOS), you can build there for much faster results.

Run these commands on your Debian/Ubuntu VM to use Cachix binary cache for faster builds:
```bash
nix-env -iA cachix -f https://cachix.org/api/v1/install
```

Enable the caches:
```bash
cachix use nix-community
cachix use lnbits
```

Then build as normal:
```bash
nix build .#nixosConfigurations.pi4.config.system.build.sdImage -L
```
