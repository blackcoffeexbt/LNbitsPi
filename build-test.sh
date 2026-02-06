#!/usr/bin/env bash
set -euo pipefail

echo "════════════════════════════════════════════════════════════"
echo "  Building Uncompressed SD Image for Testing"
echo "════════════════════════════════════════════════════════════"
echo ""

# Build the uncompressed image
echo "Building uncompressed image..."
nix build .#sdImageUncompressed -L

echo ""
echo "Build complete!"
echo ""

# Find the image file
IMAGE_FILE=$(find result/sd-image -name "*.img" -type f | head -n 1)

if [ -z "$IMAGE_FILE" ]; then
  echo "Error: Could not find .img file in result/sd-image/"
  exit 1
fi

# Get just the filename
IMAGE_NAME=$(basename "$IMAGE_FILE")

# Copy to repo root
echo "Copying image to repository root..."
cp -v "$IMAGE_FILE" "./$IMAGE_NAME"

echo ""
echo "════════════════════════════════════════════════════════════"
echo "  ✓ Done!"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "Image location: ./$IMAGE_NAME"
echo ""
echo "To flash to SD card:"
echo "  sudo dd if=./$IMAGE_NAME of=/dev/sdX bs=4M status=progress conv=fsync"
echo ""
echo "Replace /dev/sdX with your SD card device (find with: lsblk)"
echo ""
