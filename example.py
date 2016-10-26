#!/usr/bin/python

import linenoise

def main():

  x = linenoise.linenoise()
  x.history_load('history.txt')

  while True:
    line = x.read('hello> ')
    if line == 'quit':
      break
    elif line.startswith('/'):
      if line.startswith('/historylen'):
        l = line.split(' ')
        if len(l) >= 2:
          n = int(l[1], 10)
          x.history_set_maxlen(n)
        else:
          print('no history length')
      else:
        print('unrecognized command: %s' % line)
    elif len(line):
      print("echo: '%s'" % line)
      x.history_add(line)
      x.history_save("history.txt")

main()
