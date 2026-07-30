#!/bin/bash
# Elevated setup for wasm project.
# Run with: sudo bash requirements.sh

echo "Updating package lists..."
apt-get update

echo "Installing build dependencies..."
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  build-essential \
  cmake \
  ninja-build \
  git \
  pkg-config \
  python3-dev \
  libpng-dev \
  zlib1g-dev \
  clang \
  lld \
  llvm

echo "Done. Re-run your normal user shell to pick up any PATH changes."
