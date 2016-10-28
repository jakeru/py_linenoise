#!/usr/bin/python

import sys
import linenoise

def completion(s):
  """return a list of line completions"""
  if len(s) >= 1 and s[0] == 'h':
    return ('hello', 'hello there')
  return None

def hints(s):
  if s == 'hello':
    # color, bold, string
    return (35, False, ' World')
  return None

def main():
  ln = linenoise.linenoise()

  # Parse options
  argc = len(sys.argv)
  idx = 0
  while argc > 1:
    argc -= 1
    idx += 1
    argv = sys.argv[idx]
    if argv == '--multiline':
      ln.set_multiline(True)
      sys.stdout.write('Multi-line mode enabled.\n')
    elif argv == '--keycodes':
      ln.print_keycodes()
      sys.exit(0)
    else:
      sys.stderr.write('Usage: %s [--multiline] [--keycodes]\n' % sys.argv[0])
      sys.exit(1)

  # Set the completion callback. This will be called
  # every time the user uses the <tab> key.
  ln.set_completion_callback(completion)
  ln.set_hints_callback(hints)

  # Load history from file. The history file is just a plain text file
  # where entries are separated by newlines.
  ln.history_load('history.txt')

  # Now this is the main loop of the typical linenoise-based application.
  # The call to linenoise() will block until the user types something
  # and presses enter.
  while True:
    line = ln.read('hello> ')
    if line is None:
      break
    elif line.startswith('/'):
      if line.startswith('/historylen'):
        l = line.split(' ')
        if len(l) >= 2:
          n = int(l[1], 10)
          ln.history_set_maxlen(n)
        else:
          print('no history length')
      else:
        print('unrecognized command: %s' % line)
    elif len(line):
      print("echo: '%s'" % line)
      ln.history_add(line)
      ln.history_save("history.txt")

  sys.exit(0)

main()
