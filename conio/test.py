#!/usr/bin/python

import conio

def main():

  conio.init()
  #conio.key_codes()

  while True:
    line = conio.readline('stuff> ')
    if line == 'quit':
      break
    else:
      print line

main()
