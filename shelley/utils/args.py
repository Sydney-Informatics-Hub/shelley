"""Argument-parsing helpers shared by the CLI and interactive dispatchers."""

import re


def parse_verbose(args: list[str]) -> tuple[bool, list[str]]:
    """Split the verbose flag from positional args.

    Any of ``-v``, ``--verbose``, or ``-vv`` (etc.) sets ``verbose = True``.
    Returns ``(verbose, positionals)``.
    """
    verbose = False
    positional: list[str] = []
    for arg in args:
        if arg == "--verbose" or re.fullmatch(r"-v+", arg):
            verbose = True
        else:
            positional.append(arg)
    return verbose, positional


def parse_build_flags(args: list[str]) -> tuple[bool, list[str]]:
    """Split ``build`` flags from positional args.

    Recognises ``--interactive``/``-i``, which opens an interactive session to
    curate the aliases the module exposes — deselect, rename, and add — for both
    upstream and local builds. Returns ``(interactive, positionals)``.
    """
    interactive = False
    positional: list[str] = []
    for arg in args:
        if arg in ("--interactive", "-i"):
            interactive = True
        else:
            positional.append(arg)
    return interactive, positional


def parse_force_flag(args: list[str]) -> tuple[bool, list[str]]:
    """Split ``clean`` flags from positional args.

    Recognises ``-y``, which skips the interactive removal confirmation.
    Returns ``(force, positionals)``.
    """
    force = False
    positional: list[str] = []
    for arg in args:
        if arg == "-y":
            force = True
        else:
            positional.append(arg)
    return force, positional
