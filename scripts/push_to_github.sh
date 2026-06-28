#!/usr/bin/env bash
set -euo pipefail

repo="${1:-protein_design}"
visibility="${GITHUB_VISIBILITY:-private}"

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI is not installed on this host." >&2
  exit 10
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "GitHub CLI is not authenticated on this host." >&2
  echo "Run: gh auth login --git-protocol ssh" >&2
  exit 11
fi

if [ -n "$(git status --porcelain)" ]; then
  echo "Working tree is not clean; commit or discard changes before push." >&2
  git status --short >&2
  exit 12
fi

if gh repo view "$repo" >/dev/null 2>&1; then
  remote_url="$(gh repo view "$repo" --json sshUrl --jq .sshUrl)"
  git remote remove origin >/dev/null 2>&1 || true
  git remote add origin "$remote_url"
  git push -u origin main
else
  if [ "$visibility" = "public" ]; then
    gh repo create "$repo" --public --source . --remote origin --push
  else
    gh repo create "$repo" --private --source . --remote origin --push
  fi
fi

git remote -v
