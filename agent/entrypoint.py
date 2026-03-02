#!/usr/bin/env python3
"""Expand env vars in argfile.yml and run aca-py. Use ${VAR} or $VAR in the yaml."""
import os

ARG_FILE = "/app/argfile.yml"
OUT_FILE = "/tmp/argfile.yml"


def main():
    with open(ARG_FILE, "r") as f:
        content = f.read()
    expanded = os.path.expandvars(content)
    with open(OUT_FILE, "w") as f:
        f.write(expanded)
    os.execvp("aca-py", ["aca-py", "start", "--arg-file", OUT_FILE])


if __name__ == "__main__":
    main()
