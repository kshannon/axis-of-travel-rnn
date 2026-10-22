#!/usr/bin/env bash
# New files from templates/, run by pixi run new-eda, new-experiment and new-labnote:
#   new.sh eda "title"                   notebooks/eda/<date>_<slug>.ipynb
#   new.sh experiment "title" [config]   notebooks/experiments/<date>_<slug>/ with notebook.ipynb and config.yaml, a copy of
#                                        configs/experiments/<config, default baseline>.yaml
#   new.sh labnote ["title"]             labnotebook/<date>.md, or <date>__<slug>.md with a title
# The slug is the title lowercased, every run of other characters one dash, no outer dashes. An existing target is refused.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TEMPLATES="$ROOT/templates"
EDA_DIR="$ROOT/notebooks/eda"
EXPERIMENTS_DIR="$ROOT/notebooks/experiments"
LABNOTE_DIR="$ROOT/labnotebook"
EXPERIMENT_CONFIGS="configs/experiments"
DEFAULT_CONFIG="baseline"
TODAY="$(date +%Y-%m-%d)"
CREATED="$(date +%Y-%m-%dT%H:%M:%S%z)"
AUTHOR="$(git -C "$ROOT" config user.name || true)"

refuse() { echo "error: $1" >&2; exit 2; }

slug_of() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//'; }

# A value made safe for a json string (notebooks) and for the right side of a sed substitution with | as its delimiter.
escape() { printf '%s' "$1" | sed -e 's/[\\"]/\\&/g' -e 's/[\\|&]/\\&/g'; }

# Copy template $1 to $2 with every placeholder filled, title $3 and name $4.
fill() {
    sed -e "s|{{TITLE}}|$(escape "$3")|g" -e "s|{{DATE}}|$TODAY|g" -e "s|{{AUTHOR}}|$(escape "$AUTHOR")|g" \
        -e "s|{{NAME}}|$4|g" -e "s|{{CREATED}}|$CREATED|g" "$1" > "$2"
}

kind="${1:-}"
[ $# -ge 1 ] && shift
case "$kind" in
    eda)
        title="$*"
        slug="$(slug_of "$title")"
        [ -n "$slug" ] || refuse "notebook title has no letters or digits"
        target="$EDA_DIR/${TODAY}_$slug.ipynb"
        [ ! -e "$target" ] || refuse "$target already exists"
        mkdir -p "$EDA_DIR"
        fill "$TEMPLATES/notebook-eda.ipynb" "$target" "$title" "$slug"
        ;;
    experiment)
        title="${1:-}"
        config="${2:-$DEFAULT_CONFIG}"
        slug="$(slug_of "$title")"
        [ -n "$slug" ] || refuse "experiment title has no letters or digits"
        source="$ROOT/$EXPERIMENT_CONFIGS/$config.yaml"
        [ -f "$source" ] || refuse "no experiment config $source"
        target="$EXPERIMENTS_DIR/${TODAY}_$slug"
        [ ! -e "$target" ] || refuse "$target already exists"
        mkdir -p "$target"
        fill "$TEMPLATES/notebook-experiment.ipynb" "$target/notebook.ipynb" "$title" "$slug"
        { echo "# This experiment's config, a copy of $EXPERIMENT_CONFIGS/$config.yaml when the folder was made. Edit it before the run, never after."
          cat "$source"; } > "$target/config.yaml"
        ;;
    labnote)
        if [ -n "$*" ]; then
            slug="$(slug_of "$*")"
            [ -n "$slug" ] || refuse "slug is empty after cleanup"
            target="$LABNOTE_DIR/${TODAY}__$slug.md"
            title="${slug//-/ }"
        else
            slug=""
            target="$LABNOTE_DIR/$TODAY.md"
            title="$TODAY"
        fi
        [ ! -e "$target" ] || refuse "$(basename "$target") already exists"
        mkdir -p "$LABNOTE_DIR"
        fill "$TEMPLATES/labnotebook.md" "$target" "$title" "$slug"
        ;;
    *)
        refuse "usage: new.sh eda \"title\" | experiment \"title\" [config] | labnote [\"title\"]"
        ;;
esac
echo "$target"
