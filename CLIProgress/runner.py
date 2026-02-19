# Copyright (c) 2026 Jonathan Simmonds
#
# A thin wrapper around robot that adds the CLIProgress listener and
# automatically sets its arguments.
#
import sys
import subprocess

def main():
    args = sys.argv[1:]

    # Normalize arguments to match Robot's argument handling, as documented by:
    # https://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#using-command-line-options
    # Specifically, we implement:
    # - Long options are case-insensitive and hyphen-insensitive.
    # - Values separated by space (--include tag, -i tag), equals for long
    #   (--include=tag), or no separator for short (-itag).
    # - Repeated single-value options: last value wins.
    # We ignore:
    # - Long options can be abbreviated if unique (e.g., --logle → --loglevel)
    #   - This would require hardcoding too much about Robot's CLI.
    # We split all options up and normalize their names to make them easier to
    # detect. We don't modify these values and we _only_ use them for detection,
    # in case we screwed something up in our parsing. We pass through the
    # original arg list.
    normalized_args = []
    for arg in args:
        if arg.startswith("--"):
            arg_parts = arg.split("=", 1)
            arg_name = "--" + arg_parts[0][2:].lower().replace("-", "")
            normalized_args.append(arg_name)
            if len(arg_parts) > 1:
                normalized_args.append(arg_parts[1])
        elif arg.startswith("-") and len(arg) > 2 and arg[1] != "-":
            normalized_args.append(arg[:2])
            normalized_args.append(arg[2:])
        else:
            normalized_args.append(arg)

    # Extract console colors from arguments.
    console_colors = None
    console_width = None
    for i, arg in enumerate(normalized_args):
        if arg in {"-C", "--consolecolors"} and i + 1 < len(normalized_args):
            console_colors = normalized_args[i + 1]
        elif arg in {"-W", "--consolewidth"} and i + 1 < len(normalized_args):
            console_width = normalized_args[i + 1]

    # Build the command to run robot.
    listener = "CLIProgress"
    if console_colors is not None:
        listener += f":colors={console_colors}"
    if console_width is not None:
        listener += f":width={console_width}"
    cmd = [
        "robot",
        "--console=quiet",
        "--listener",
        listener,
        *args,
    ]

    try:
        sys.exit(subprocess.call(cmd))
    except KeyboardInterrupt:
        sys.exit(130)
