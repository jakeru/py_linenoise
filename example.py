#!/usr/bin/python

import sys
import time
import linenoise

_KEY_HOTKEY = '?'

def completion(s):
  """return a list of line completions"""
  if len(s) >= 1 and s[0] == 'h':
    return ('hello', 'hello there')
  return None

def hints(s):
  """return the hints for this command"""
  if s == 'hello':
    # string, color, bold
    return (' World', 35, False)
  return None

loop_idx = 0
_LOOPS = 10

def loop():
  """example loop function - return True on completion"""
  global loop_idx
  sys.stdout.write('loop index %d/%d\r\n' % (loop_idx, _LOOPS))
  time.sleep(0.5)
  loop_idx += 1
  return loop_idx > _LOOPS

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
    elif argv == '--loop':
      print('looping: press ctrl-d to exit')
      rc = ln.loop(loop)
      print(('early exit of loop', 'loop completed')[rc])
      sys.exit(0)
    else:
      sys.stderr.write('Usage: %s [--multiline] [--keycodes] [--loop]\n' % sys.argv[0])
      sys.exit(1)

  # Set the completion callback. This will be called
  # every time the user uses the <tab> key.
  ln.set_completion_callback(completion)
  ln.set_hints_callback(hints)

  # Load history from file. The history file is a plain text file
  # where entries are separated by newlines.
  ln.history_load('history.txt')

  # Set a hotkey. A hotkey will cause the line editing to exit. The hotkey
  # will be appended to the returned line buffer but not displayed.
  ln.set_hotkey(_KEY_HOTKEY)

  # This is the main loop of a typical linenoise-based application.
  # The call to read() will block until the user types something
  # and presses enter or a hotkey.
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
      if line.endswith(_KEY_HOTKEY):
        line = line[:-1]
      ln.history_add(line)
      ln.history_save("history.txt")

  sys.exit(0)

main()
