#!/usr/bin/python

import linenoise

def main():
  x = linenoise.linenoise()

  # Load history from file. The history file is
  # just a plain text file where entries are separated by newlines.
  x.history_load('history.txt')
  x.history_set_maxlen(20)
  x.history_add('add_command0')
  x.history_add('add_command1')
  x.history_add('add_command2')
  x.history_add('add_command3')
  x.history_add('add_command4')
  x.history_save('history.txt')

  #x.print_keycodes()

  x.test()


main()
