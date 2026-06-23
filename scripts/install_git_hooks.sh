#!/bin/sh
set -eu

mkdir -p .git/hooks
cp scripts/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
echo "Installed .git/hooks/pre-commit"

