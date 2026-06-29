#!/usr/bin/env bash
set -u
BASE="${PROTEIN_DESIGN_HOME:-$HOME/protein_design}"
LOG="$BASE/docs/github_mirror_clone_$(date +%Y%m%d_%H%M%S).log"
mkdir -p "$BASE/repos" "$BASE/docs"
: > "$LOG"
repos="dauparas/LigandMPNN LigandMPNN
martinpacesa/BindCraft BindCraft
RosettaCommons/RFantibody RFantibody
sokrypton/ColabDesign ColabDesign"
mirrors="https://github.com/%s.git
https://gh.llkk.cc/https://github.com/%s.git
https://gh-proxy.com/https://github.com/%s.git
https://hub.gitmirror.com/https://github.com/%s.git
https://gitclone.com/github.com/%s.git"
printf "started\t%s\n" "$(date -Iseconds)" | tee -a "$LOG"
printf "%s\n" "$repos" | while read -r slug dir; do
  [ -n "$slug" ] || continue
  target="$BASE/repos/$dir"
  printf "\n== %s -> %s ==\n" "$slug" "$target" | tee -a "$LOG"
  if [ -d "$target/.git" ]; then
    printf "EXISTS\t%s\t%s\n" "$dir" "$(git -C "$target" rev-parse HEAD 2>/dev/null || echo unknown)" | tee -a "$LOG"
    continue
  fi
  rm -rf "$target.tmp" "$target"
  cloned=0
  printf "%s\n" "$mirrors" | while read -r fmt; do
    [ -n "$fmt" ] || continue
    url=$(printf "$fmt" "$slug")
    printf "TRY\t%s\t%s\n" "$dir" "$url" | tee -a "$LOG"
    if timeout 45 git ls-remote --heads "$url" HEAD >>"$LOG" 2>&1; then
      if timeout 180 git clone --depth=1 --filter=blob:none "$url" "$target.tmp" >>"$LOG" 2>&1; then
        git -C "$target.tmp" remote set-url origin "https://github.com/$slug.git" || true
        printf "mirror_url\t%s\n" "$url" > "$target.tmp/.codex_mirror_provenance.tsv"
        printf "upstream_url\thttps://github.com/%s.git\n" "$slug" >> "$target.tmp/.codex_mirror_provenance.tsv"
        printf "cloned_at\t%s\n" "$(date -Iseconds)" >> "$target.tmp/.codex_mirror_provenance.tsv"
        mv "$target.tmp" "$target"
        printf "CLONED\t%s\t%s\t%s\n" "$dir" "$(git -C "$target" rev-parse HEAD 2>/dev/null || echo unknown)" "$url" | tee -a "$LOG"
        cloned=1
        break
      else
        printf "CLONE_FAILED\t%s\t%s\n" "$dir" "$url" | tee -a "$LOG"
      fi
    else
      printf "LSREMOTE_FAILED\t%s\t%s\n" "$dir" "$url" | tee -a "$LOG"
    fi
  done
  if [ "$cloned" -ne 1 ] && [ ! -d "$target/.git" ]; then
    printf "FAILED_ALL\t%s\t%s\n" "$dir" "$slug" | tee -a "$LOG"
  fi
done
printf "\nrepo commits\n" > "$BASE/docs/repo_commits.tsv"
for d in "$BASE"/repos/*; do
  if [ -e "$d/.git" ]; then
    printf "%s\t%s\t%s\n" "$(basename "$d")" "$(git -C "$d" rev-parse HEAD 2>/dev/null || echo NA)" "$(git -C "$d" remote get-url origin 2>/dev/null || echo symlink)" >> "$BASE/docs/repo_commits.tsv"
  else
    printf "%s\t%s\t%s\n" "$(basename "$d")" "symlink" "$(readlink "$d" 2>/dev/null || echo local)" >> "$BASE/docs/repo_commits.tsv"
  fi
done
printf "finished\t%s\n" "$(date -Iseconds)" | tee -a "$LOG"
printf "log\t%s\n" "$LOG"
