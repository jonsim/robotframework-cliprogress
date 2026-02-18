# Copyright (c) 2026 Jonathan Simmonds
#
# A thin wrapper around robot that adds the CLIProgress listener and
# automatically sets its arguments.
#
import sys
import subprocess

def main():
    args = sys.argv[1:]

    # Extract console colors from arguments.
    console_colors = None
    for i, arg in enumerate(args):
        if arg in {"-C", "--consolecolors", "--console-colors"} and i + 1 < len(args):
            console_colors = args[i + 1]
        elif arg.startswith("-C"):
            console_colors = arg[2:]
        elif arg.startswith(("--consolecolors", "--console-colors")):
            console_colors = arg.split("=", 1)[1]

    # Build the command to run robot.
    cmd = [
        "robot",
        "--console=quiet",
        "--listener",
        f"CLIProgress:colors={console_colors}",
        *args,
    ]

    sys.exit(subprocess.call(cmd))
