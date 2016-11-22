#!/usr/bin/python

# -----------------------------------------------------------------------------

import sys
import cli

# -----------------------------------------------------------------------------

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

argument_help = (
    ('arg0', ' arg0 description'),
    ('arg1', ' arg1 description'),
    ('arg2', ' arg2 description'),
)

def a0_func(ui, args):
  """a0 function description"""
  ui.put('a0 function arguments %s\n' % str(args))

def a1_func(ui, args):
  """a1 function description"""
  ui.put('a1 function arguments %s\n' % str(args))

def a2_func(ui, args):
  """a2 function description"""
  ui.put('a2 function arguments %s\n' % str(args))

def b0_func(ui, args):
  """b0 function description"""
  ui.put('b0 function arguments %s\n' % str(args))

def b1_func(ui, args):
  """b1 function description"""
  ui.put('b1 function arguments %s\n' % str(args))

def c0_func(ui, args):
  """c0 function description"""
  ui.put('c0 function arguments %s\n' % str(args))

def c1_func(ui, args):
  """c1 function description"""
  ui.put('c1 function arguments %s\n' % str(args))

def c2_func(ui, args):
  """c2 function description"""
  ui.put('c2 function arguments %s\n' % str(args))

a_menu = (
  ('a0', a0_func, argument_help),
  ('a1', a1_func, argument_help),
  ('a2', a2_func),
)

b_menu = (
  ('b0', b0_func, argument_help),
  ('b1', b1_func),
)

c_menu = (
  ('c0', c0_func, argument_help),
  ('c1', c1_func, argument_help),
  ('c2', c2_func),
)

menu_root = (
  ('a', a_menu, 'a functions'),
  ('b', b_menu, 'b functions'),
  ('c', c_menu, 'c functions'),
  ('exit', cmd_exit),
  ('help', cmd_help),
  ('history', cmd_history, cli.history_help),
)

# -----------------------------------------------------------------------------

class user_interface(object):

  def __init__(self):
    pass

  def put(self, s):
    sys.stdout.write(s)

# -----------------------------------------------------------------------------

ui = user_interface()
cli = cli.cli(ui, 'history.txt')
cli.set_root(menu_root)
cli.set_prompt('cli> ')

def main():
  cli.run()
  sys.exit(0)

main()

# -----------------------------------------------------------------------------
