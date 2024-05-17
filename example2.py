#!/usr/bin/python3

# -----------------------------------------------------------------------------

import sys
import cli
import time

# -----------------------------------------------------------------------------
# cli related leaf functions


def cmd_help(ui, args):
    """general help"""
    cli.general_help()


def cmd_history(ui, args):
    """command history"""
    return cli.display_history(args)


def cmd_exit(ui, args):
    """exit application"""
    cli.exit()


# -----------------------------------------------------------------------------
# application leaf functions

loop_idx = 0
_LOOPS = 10


def loop(ui):
    """example loop function - return True on completion"""
    global loop_idx
    sys.stdout.write("loop index %d/%d\r\n" % (loop_idx, _LOOPS))
    time.sleep(0.5)
    loop_idx += 1
    return loop_idx > _LOOPS


def a0_func(ui, args):
    """a0 function description"""
    global cli, loop_idx
    ui.put("a0 function arguments %s\n" % str(args))
    ui.put("Looping... Ctrl-D to exit\n")
    loop_idx = 0
    cli.ln.loop(lambda: loop(ui))


def a1_func(ui, args):
    """a1 function description"""
    ui.put("a1 function arguments %s\n" % str(args))


def a2_func(ui, args):
    """a2 function description"""
    ui.put("a2 function arguments %s\n" % str(args))


def b0_func(ui, args):
    """b0 function description"""
    ui.put("b0 function arguments %s\n" % str(args))


def b1_func(ui, args):
    """b1 function description"""
    ui.put("b1 function arguments %s\n" % str(args))


def c0_func(ui, args):
    """c0 function description"""
    ui.put("c0 function arguments %s\n" % str(args))


def c1_func(ui, args):
    """c1 function description"""
    ui.put("c1 function arguments %s\n" % str(args))


def c2_func(ui, args):
    """c2 function description"""
    ui.put("c2 function arguments %s\n" % str(args))


# -----------------------------------------------------------------------------
"""
Menu Tree

(name, submenu, description) - reference to submenu
(name, leaf) - leaf command with generic <cr> help
(name, leaf, help) - leaf command with specific argument help

Note: The general help for a leaf function is the docstring for the leaf function.
"""

# example of function argument help (parm, descr)
argument_help = (
    ("arg0", "arg0 description"),
    ("arg1", "arg1 description"),
    ("arg2", "arg2 description"),
)

# 'a' submenu items
a_menu = (
    ("a0", a0_func, argument_help),
    ("a1", a1_func, argument_help),
    ("a2", a2_func),
)

# 'b' submenu items
b_menu = (
    ("b0", b0_func, argument_help),
    ("b1", b1_func),
)

# 'c' submenu items
c_menu = (
    ("c0", c0_func, argument_help),
    ("c1", c1_func, argument_help),
    ("c2", c2_func),
)

# root menu
menu_root = (
    ("amenu", a_menu, "menu a functions"),
    ("bmenu", b_menu, "menu b functions"),
    ("cmenu", c_menu, "menu c functions"),
    ("exit", cmd_exit),
    ("help", cmd_help),
    ("history", cmd_history, cli.history_help),
)

# -----------------------------------------------------------------------------


class user_interface(object):
    """
    Each leaf function is called with an instance of this object.
    The user can extend this class with application specific functions.
    """

    def __init__(self):
        pass

    def put(self, s):
        """print a string to stdout"""
        sys.stdout.write(s)


# -----------------------------------------------------------------------------

# setup the cli object
cli = cli.cli(user_interface(), "history.txt")
cli.set_root(menu_root)
cli.set_prompt("cli> ")


def main():
    cli.run()
    sys.exit(0)


main()

# -----------------------------------------------------------------------------
