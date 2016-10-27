# -----------------------------------------------------------------------------
"""

linenoise for python

See: http://github.com/antirez/linenoise

"""
# -----------------------------------------------------------------------------

import os
import stat
import sys
import atexit
import termios
import struct
import fcntl
import string

# -----------------------------------------------------------------------------

DEFAULT_HISTORY_MAX_LEN = 100

STDIN_FILENO = sys.stdin.fileno()
STDOUT_FILENO = sys.stdout.fileno()

# indices within the termios settings
C_IFLAG = 0
C_OFLAG = 1
C_CFLAG = 2
C_LFLAG = 3
C_CC = 6

# key codes
KEY_NULL = 0    # NULL
CTRL_A = 1      # Ctrl+a
CTRL_B = 2      # Ctrl-b
CTRL_C = 3      # Ctrl-c
CTRL_D = 4      # Ctrl-d
CTRL_E = 5      # Ctrl-e
CTRL_F = 6      # Ctrl-f
CTRL_H = 8      # Ctrl-h
TAB = 9         # Tab
CTRL_K = 11     # Ctrl+k
CTRL_L = 12     # Ctrl+l
ENTER = 13      # Enter
CTRL_N = 14     # Ctrl-n
CTRL_P = 16     # Ctrl-p
CTRL_T = 20     # Ctrl-t
CTRL_U = 21     # Ctrl+u
CTRL_W = 23     # Ctrl+w
ESC = 27        # Escape
BACKSPACE = 127 # Backspace

# -----------------------------------------------------------------------------

# if we can't work out how many columns the terminal has use this value
DEFAULT_COLS = 80

def get_cursor_position(ifd, ofd):
  """Get the horizontal cursor position"""
  # query the cursor location
  if os.write(ofd, '\x1b[6n') != 4:
    return -1
  # read the response: ESC [ rows ; cols R
  # rows/cols are decimal number strings
  buf = []
  while len(buf) < 32:
    buf.append(os.read(ifd, 1))
    if buf[-1] == 'R':
      break
  # parse it
  if buf[0] != chr(ESC) or buf[1] != '[' or buf[-1] != 'R':
    return -1
  buf = buf[2:-1]
  (_, cols) = ''.join(buf).split(';')
  # return the cols
  return int(cols, 10)

def get_columns(ifd, ofd):
  """Get the number of columns for the terminal. Assume DEFAULT_COLS if it fails."""
  cols = 0
  # try using the ioctl to get the number of cols
  try:
    t = fcntl.ioctl(STDOUT_FILENO, termios.TIOCGWINSZ, struct.pack('HHHH', 0, 0, 0, 0))
    (_, cols, _, _) = struct.unpack('HHHH', t)
  except:
    pass
  if cols == 0:
    # the ioctl failed - try using the terminal itself
    start = get_cursor_position(ifd, ofd)
    if start < 0:
      return DEFAULT_COLS
    # Go to right margin and get position
    if os.write(ofd, '\x1b[999C') != 6:
      return DEFAULT_COLS
    cols = get_cursor_position(ifd, ofd)
    if cols < 0:
      return DEFAULT_COLS
    # restore the position
    if cols > start:
      os.write(ofd, '\x1b[%dD' % (cols - start))
  return cols

def clear_screen():
  """Clear the screen"""
  sys.stdout.write('\x1b[H\x1b[2J')
  sys.stdout.flush()

def beep():
  """Beep"""
  sys.stderr.write('\x07')
  sys.stderr.flush()

# -----------------------------------------------------------------------------

def unsupported_term():
  """return True if we know we don't support this terminal"""
  unsupported = ('dumb', 'cons25', 'emacs')
  term = os.environ.get('TERM', '')
  return term in unsupported

# -----------------------------------------------------------------------------

class line_state(object):
  """line editing state"""

  def __init__(self, ifd, ofd, prompt):
    self.ifd = ifd                    # stdin file descriptor
    self.ofd = ofd                    # stdout file descriptor
    self.buf = []                     # line buffer
    self.prompt = prompt              # prompt string
    self.pos = 0                      # current cursor position within line buffer
    self.oldpos = 0                   # previous refresh cursor position
    self.cols = get_columns(ifd, ofd) # number of columns in terminal
    self.maxrows = 0                  # maximum num of rows used so far (multiline mode)
    self.history_index = 0            # history index we are currently editing
    self.mlmode = False               # are we in multiline mode?

  def refresh_singleline(self):
    """single line refresh"""
    seq = []
    plen = len(self.prompt)
    blen = len(self.buf)
    idx = 0
    pos = self.pos
    # scroll the characters to the left if we are at max columns
    while (plen + pos) >= self.cols:
      idx += 1
      blen -= 1
      pos -= 1
    while (plen + blen) > self.cols:
      blen -= 1
    # cursor to the left edge
    seq.append('\r')
    # write the prompt
    seq.append(self.prompt)
    # write the current buffer content
    seq.append(''.join([chr(self.buf[i]) for i in range(idx, idx + blen)]))
    # Show hints (if any)
    # TODO refreshShowHints(&ab,l,plen);
    # Erase to right
    seq.append('\x1b[0K')
    # Move cursor to original position
    seq.append('\r\x1b[%dC' % (plen + pos))
    # write it out
    os.write(self.ofd, ''.join(seq))

  def refresh_multiline(self):
    """multiline refresh"""
    pass

  def refresh_line(self):
    """refresh the edit line"""
    if self.mlmode:
      self.refresh_multiline()
    else:
      self.refresh_singleline()

  def edit_delete(self):
    """delete the character at the current cursor position"""
    if len(self.buf) > 0 and self.pos < len(self.buf):
      self.buf.pop(self.pos)
      self.refresh_line()

  def edit_backspace(self):
    """delete the character to the left of the current cursor position"""
    if self.pos > 0 and len(self.buf) > 0:
      self.buf.pop(self.pos - 1)
      self.pos -= 1
      self.refresh_line()

  def edit_insert(self, c):
    """insert a character at the current cursor position"""
    self.buf.insert(self.pos, c)
    self.pos += 1
    self.refresh_line()

  def edit_swap(self):
    """swap current character with the previous character"""
    if self.pos > 0 and self.pos < len(self.buf):
      tmp = self.buf[self.pos - 1]
      self.buf[self.pos - 1] = self.buf[self.pos]
      self.buf[self.pos] = tmp
      if self.pos != len(self.buf) - 1:
        self.pos += 1
      self.refresh_line()

  def edit_history(self, s):
    """set the line buffer to a history string"""
    self.buf = [ord(c) for c in s]
    self.pos = len(self.buf)
    self.refresh_line()

  def edit_move_left(self):
    """Move cursor on the left"""
    if self.pos > 0:
      self.pos -= 1
      self.refresh_line()

  def edit_move_right(self):
    """Move cursor to the right"""
    if self.pos != len(self.buf):
      self.pos += 1
      self.refresh_line()

  def edit_move_home(self):
    """move to the start of the line buffer"""
    if self.pos:
      self.pos = 0
      self.refresh_line()

  def edit_move_end(self):
    """move to the end of the line buffer"""
    if self.pos != len(self.buf):
      self.pos = len(self.buf)
      self.refresh_line()

  def delete_line(self):
    """delete the line"""
    self.buf = []
    self.pos = 0
    self.refresh_line()

  def delete_to_end(self):
    """delete from the current cursor postion to the end of the line"""
    self.buf = self.buf[:self.pos]
    self.refresh_line()

  def delete_prev_word(self):
    """delete the previous space delimited word in the line buffer"""
    # TODO
    pass

  def __str__(self):
    """return a string for the line buffer"""
    return ''.join([chr(c) for c in self.buf])

# -----------------------------------------------------------------------------

class linenoise(object):
  """terminal state"""

  def __init__(self):
    self.history = [] # list of history strings
    self.history_maxlen = DEFAULT_HISTORY_MAX_LEN # maximum number of history entries
    self.rawmode = False # are we in raw mode?
    self.atexit_registered = False # have we registered a cleanup upon exit function?

  def enable_rawmode(self, fd):
    """Enable raw mode"""
    if not os.isatty(fd):
      return -1
    # cleanup upon disaster
    if not self.atexit_registered:
      atexit.register(self.atexit)
      self.atexit_registered = True
    # modify the original mode
    self.orig_termios = termios.tcgetattr(fd)
    raw = termios.tcgetattr(fd)
    # input modes: no break, no CR to NL, no parity check, no strip char, no start/stop output control
    raw[C_IFLAG] &= ~(termios.BRKINT | termios.ICRNL | termios.INPCK | termios.ISTRIP | termios.IXON)
    # output modes - disable post processing
    raw[C_OFLAG] &= ~(termios.OPOST)
    # control modes - set 8 bit chars
    raw[C_CFLAG] |= (termios.CS8)
    # local modes - echo off, canonical off, no extended functions, no signal chars (^Z,^C)
    raw[C_LFLAG] &= ~(termios.ECHO | termios.ICANON | termios.IEXTEN | termios.ISIG)
    # control chars - set return condition: min number of bytes and timer.
    # We want read to return every single byte, without timeout.
    raw[C_CC][termios.VMIN] = 1
    raw[C_CC][termios.VTIME] = 0
    # put terminal in raw mode after flushing
    termios.tcsetattr(fd, termios.TCSAFLUSH, raw)
    self.rawmode = True
    return 0

  def disable_rawmode(self, fd):
    """Disable raw mode"""
    if self.rawmode:
      termios.tcsetattr(fd, termios.TCSAFLUSH, self.orig_termios)
      self.rawmode = False

  def atexit(self):
    """Restore STDIN to the orignal mode"""
    sys.stdout.write('\r')
    sys.stdout.flush()
    self.disable_rawmode(STDIN_FILENO)


  def edit(self, ifd, ofd, prompt):
    """edit a line in raw mode"""
    # create the line state
    ls = line_state(ifd, ofd, prompt)
    # The latest history entry is always our current buffer, initially an empty string
    self.history_add('')
    # output the prompt
    if os.write(ofd, prompt) != len(prompt):
      return None
    while True:
      c = ord(os.read(ifd, 1))
      if c == ENTER:
        self.history.pop()
        return str(ls)
      elif c == BACKSPACE:
        # backspace: remove the character to the left of the cursor
        ls.edit_backspace()
      elif c == ESC:
        # escape sequence
        s0 = os.read(ifd, 1)
        s1 = os.read(ifd, 1)
        if s0 == '[':
          # ESC [ sequence
          if s1 >= '0' and s1 <= '9':
            pass
          else:
            if s1 == 'A':
              # cursor up
              ls.edit_history('prev_history')
            elif s1 == 'B':
              # cursor down
              ls.edit_history('next_history')
            elif s1 == 'C':
              # cursor right
              ls.edit_move_right()
            elif s1 == 'D':
              # cursor left
              ls.edit_move_left()
            elif s1 == 'H':
              # cursor home
              ls.edit_move_home()
            elif s1 == 'F':
              # cursor end
              ls.edit_move_end()
        elif s0 == '0':
          # ESC 0 sequence
          if s1 == 'H':
            # cursor home
            ls.edit_move_home()
          elif s1 == 'F':
            # cursor end
            ls.edit_move_end()
        else:
          pass
      elif c == CTRL_A:
        # go to the start of the line
        ls.edit_move_home()
      elif c == CTRL_B:
        # cursor left
        ls.edit_move_left()
      elif c == CTRL_C:
        # return None == EOF
        return None
      elif c == CTRL_D:
        # delete: remove the character to the right of the cursor.
        # If the line is empty act as an EOF.
        if len(ls.buf):
          ls.edit_delete()
        else:
          self.history.pop()
          return None
      elif c == CTRL_E:
        # go to the end of the line
        ls.edit_move_end()
      elif c == CTRL_F:
        # cursor right
        ls.edit_move_right()
      elif c == CTRL_H:
        # backspace: remove the character to the left of the cursor
        ls.edit_backspace()
      elif c == CTRL_K:
        # delete to the end of the line
        ls.delete_to_end()
      elif c == CTRL_L:
        # clear screen
        clear_screen()
        ls.refresh_line()
      elif c == CTRL_N:
        # next history item
        ls.edit_history('next_history')
      elif c == CTRL_P:
        # previous history item
        ls.edit_history('prev_history')
      elif c == CTRL_T:
        # swap current character with the previous
        ls.edit_swap()
      elif c == CTRL_U:
        # delete the whole line
        ls.delete_line()
      elif c == CTRL_W:
        # delete previous word
        ls.delete_prev_word()
      else:
        # insert the character into the line buffer
        ls.edit_insert(c)

  def read_raw(self, prompt):
    """read a line from stdin in raw mode"""
    if self.enable_rawmode(STDIN_FILENO) == -1:
      return None
    s = self.edit(STDIN_FILENO, STDOUT_FILENO, prompt)
    self.disable_rawmode(STDIN_FILENO)
    sys.stdout.write('\r\n')
    return s

  def read(self, prompt):
    """Read a line. Return None on EOF"""
    if not os.isatty(STDIN_FILENO):
      # Not a tty. Read from a file/pipe.
      s = sys.stdin.readline().strip('\n')
      return (s, None)[s == '']
    elif unsupported_term():
      # Not a terminal we know about. So basic line reading.
      try:
        s = raw_input(prompt)
      except EOFError:
        s = None
      return s
    else:
      return self.read_raw(prompt)

  def print_keycodes(self):
    """Print scan codes on screen for debugging/development purposes"""
    print("Linenoise key codes debugging mode.")
    print("Press keys to see scan codes. Type 'quit' at any time to exit.")
    if self.enable_rawmode(STDIN_FILENO) != 0:
      return
    cmd = [''] * 4
    while True:
      # get a character
      c = os.read(STDIN_FILENO, 1)
      if c == '':
        continue
      # display the character
      if c in string.printable:
        m = {'\r': '\\r', '\n': '\\n', '\t': '\\t'}
        cstr = m.get(c, c)
      else:
        m = {0x1b: 'ESC'}
        cstr = m.get(ord(c), '?')
      sys.stdout.write("'%s' 0x%02x (%d)\r\n" % (cstr, ord(c), ord(c)))
      sys.stdout.flush()
      # check for quit
      cmd = cmd[1:]
      cmd.append(c)
      if ''.join(cmd) == 'quit':
        break
    # restore the original mode
    self.disable_rawmode(STDIN_FILENO)

  def history_add(self, line):
    """Add a new entry to the history"""
    if self.history_maxlen == 0:
      return
    # don't add duplicated lines
    for l in self.history:
      if l == line:
        return
    # add the line to the history
    if len(self.history) == self.history_maxlen:
      # remove the first entry
      self.history.pop(0)
    self.history.append(line)

  def history_set_maxlen(self, n):
    """Set the maximum length for the history. Truncate the current history if needed."""
    if n < 0:
      return
    self.history_maxlen = n
    current_length = len(self.history)
    if current_length > self.history_maxlen:
      # truncate and retain the latest history
      self.history = self.history[current_length - self.history_maxlen:]

  def history_save(self, fname):
    """Save the history to a file"""
    old_umask = os.umask(stat.S_IXUSR | stat.S_IRWXG | stat.S_IRWXO)
    f = open(fname, 'w')
    os.umask(old_umask)
    os.chmod(fname, stat.S_IRUSR | stat.S_IWUSR)
    f.write('\n'.join(self.history))
    f.close()

  def history_load(self, fname):
    """Load history from a file"""
    self.history = []
    if os.path.isfile(fname):
      f = open(fname, 'r')
      x = f.readlines()
      f.close()
      self.history = [l.strip() for l in x]

# -----------------------------------------------------------------------------



