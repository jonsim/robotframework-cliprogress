# Copyright (c) 2026 Jonathan Simmonds
#
# A thin wrapper around robot that adds the CLIProgress listener and
# automatically sets its arguments.
#
import subprocess
import sys


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
    # We also remove custom arguments from the arg list, so that they don't get
    # passed through to Robot.
    normalized_args = []
    robot_args = []
    skip_next_arg = False
    for arg in args:
        if arg.startswith("--"):
            arg_parts = arg.split("=", 1)
            arg_name = "--" + arg_parts[0][2:].lower().replace("-", "")
            normalized_args.append(arg_name)
            if len(arg_parts) > 1:
                normalized_args.append(arg_parts[1])
            if arg_name not in {"--consolestatus"}:
                robot_args.append(arg)
            elif len(arg_parts) == 1:
                skip_next_arg = True
        elif arg.startswith("-") and len(arg) > 2 and arg[1] != "-":
            normalized_args.append(arg[:2])
            normalized_args.append(arg[2:])
            robot_args.append(arg)
        else:
            normalized_args.append(arg)
            if not skip_next_arg:
                robot_args.append(arg)
            else:
                skip_next_arg = False

    # Extract console colors and width from arguments.
    console_colors = None
    console_width = None
    console_status = None
    for i, arg in enumerate(normalized_args):
        if arg in {"-C", "--consolecolors"} and i + 1 < len(normalized_args):
            console_colors = normalized_args[i + 1]
        elif arg in {"-W", "--consolewidth"} and i + 1 < len(normalized_args):
            console_width = normalized_args[i + 1]
        elif arg in {"--consolestatus"} and i + 1 < len(normalized_args):
            console_status = normalized_args[i + 1]

    # Build the command to run robot.
    listener = "CLIProgress"
    if console_colors is not None:
        listener += f":colors={console_colors}"
    if console_width is not None:
        listener += f":width={console_width}"
    if console_status is not None:
        listener += f":console_status={console_status}"
    cmd = [
        "robot",
        "--console=none",
        "--listener",
        listener,
        *robot_args,
    ]
    print(f"Running command: {' '.join(cmd)}")

    try:
        sys.exit(subprocess.call(cmd))
    except KeyboardInterrupt:
        sys.exit(130)
