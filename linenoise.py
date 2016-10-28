# -----------------------------------------------------------------------------
"""

linenoise for python

See: https://github.com/deadsy/py_linenoise

Based on: http://github.com/antirez/linenoise

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

# indices within the termios array
C_IFLAG = 0
C_OFLAG = 1
C_CFLAG = 2
C_LFLAG = 3
C_CC = 6

# -----------------------------------------------------------------------------

# Key Codes
_KEY_NULL = chr(0)
_KEY_CTRL_A = chr(1)
_KEY_CTRL_B = chr(2)
_KEY_CTRL_C = chr(3)
_KEY_CTRL_D = chr(4)
_KEY_CTRL_E = chr(5)
_KEY_CTRL_F = chr(6)
_KEY_CTRL_H = chr(8)
_KEY_TAB = chr(9)
_KEY_CTRL_K = chr(11)
_KEY_CTRL_L = chr(12)
_KEY_ENTER = chr(13)
_KEY_CTRL_N = chr(14)
_KEY_CTRL_P = chr(16)
_KEY_CTRL_T = chr(20)
_KEY_CTRL_U = chr(21)
_KEY_CTRL_W = chr(23)
_KEY_ESC = chr(27)
_KEY_BS = chr(127)

# -----------------------------------------------------------------------------

_STDIN = sys.stdin.fileno()
_STDOUT = sys.stdout.fileno()
_STDERR = sys.stderr.fileno()

def _getc(fd, timeout=-1):
  """
    read a single character from a file (with timeout)
    timeout = 0 : return immediately
    timeout < 0 : wait for the character (block)
    timeout > 0 : wait for timeout seconds
  """
  pass

def _puts(fd, s):
  """write a string to a file, return the number of characters written"""
  return os.write(fd, s)

# -----------------------------------------------------------------------------

# Use this value if we can't work out how many columns the terminal has.
_DEFAULT_COLS = 80

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
  if buf[0] != _KEY_ESC or buf[1] != '[' or buf[-1] != 'R':
    return -1
  buf = buf[2:-1]
  (_, cols) = ''.join(buf).split(';')
  # return the cols
  return int(cols, 10)

def get_columns(ifd, ofd):
  """Get the number of columns for the terminal. Assume _DEFAULT_COLS if it fails."""
  cols = 0
  # try using the ioctl to get the number of cols
  try:
    t = fcntl.ioctl(_STDOUT, termios.TIOCGWINSZ, struct.pack('HHHH', 0, 0, 0, 0))
    (_, cols, _, _) = struct.unpack('HHHH', t)
  except:
    pass
  if cols == 0:
    # the ioctl failed - try using the terminal itself
    start = get_cursor_position(ifd, ofd)
    if start < 0:
      return _DEFAULT_COLS
    # Go to right margin and get position
    if os.write(ofd, '\x1b[999C') != 6:
      return _DEFAULT_COLS
    cols = get_cursor_position(ifd, ofd)
    if cols < 0:
      return _DEFAULT_COLS
    # restore the position
    if cols > start:
      os.write(ofd, '\x1b[%dD' % (cols - start))
  return cols

# -----------------------------------------------------------------------------

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

  def __init__(self, ifd, ofd, prompt, mlmode):
    self.ifd = ifd                    # stdin file descriptor
    self.ofd = ofd                    # stdout file descriptor
    self.buf = []                     # line buffer
    self.prompt = prompt              # prompt string
    self.pos = 0                      # current cursor position within line buffer
    self.oldpos = 0                   # previous refresh cursor position
    self.cols = get_columns(ifd, ofd) # number of columns in terminal
    self.maxrows = 0                  # maximum num of rows used so far (multiline mode)
    self.history_idx = 0              # history index we are currently editing, 0 is the LAST entry
    self.mlmode = mlmode              # are we in multiline mode?

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
    seq.append(''.join([self.buf[i] for i in range(idx, idx + blen)]))
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

  def edit_set(self, s):
    """set the line buffer to a string"""
    if s is None:
      return
    self.buf = list(s)
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

  def complete_line(self, callback):
    """show completions for the current line"""
    c = 0
    # get a list of line completions
    lc = callback(str(self))
    if lc is None or len(lc) == 0:
      # no line completions
      beep()
    else:
      # navigate and display the line completions
      stop = False
      idx = 0
      while not stop:
        if idx < len(lc):
          # show the completion
          saved_buf = self.buf
          saved_pos = self.pos
          # show the completion
          self.buf = list(lc[idx])
          self.pos = len(self.buf)
          self.refresh_line()
          # restore the line buffer
          self.buf = saved_buf
          self.pos = saved_pos
        else:
          # show the original buffer
          self.refresh_line()
        # navigate through the completions
        c = os.read(self.ifd, 1)
        if c == _KEY_TAB:
          # loop through the completions
          idx = (idx + 1) % (len(lc) + 1)
          if idx == len(lc):
            beep()
        elif c == _KEY_ESC:
          # re-show the original buffer
          if idx < len(lc):
            self.refresh_line()
          stop = True
        else:
          # update the buffer and return
          if idx < len(lc):
            self.buf = list(lc[idx])
            self.pos = len(self.buf)
          stop = True
    # return the last character read
    return c

  def __str__(self):
    """return a string for the line buffer"""
    return ''.join(self.buf)

# -----------------------------------------------------------------------------

class linenoise(object):
  """terminal state"""

  def __init__(self):
    self.history = []               # list of history strings
    self.history_maxlen = 32        # maximum number of history entries (default)
    self.rawmode = False            # are we in raw mode?
    self.mlmode = False             # are we in multiline mode?
    self.atexit_flag = False        # have we registered a cleanup upon exit function?
    self.orig_termios = None        # saved termios attributes
    self.completion_callback = None # callback function for tab completion
    self.hints_callback = None      # callback function for hints

  def enable_rawmode(self, fd):
    """Enable raw mode"""
    if not os.isatty(fd):
      return -1
    # ensure cleanup upon exit/disaster
    if not self.atexit_flag:
      atexit.register(self.atexit)
      self.atexit_flag = True
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
    self.disable_rawmode(_STDIN)

  def edit(self, ifd, ofd, prompt):
    """edit a line in raw mode"""
    # create the line state
    ls = line_state(ifd, ofd, prompt, self.mlmode)
    # The latest history entry is always our current buffer, initially an empty string
    self.history_add('')
    # output the prompt
    if os.write(ofd, prompt) != len(prompt):
      return None
    while True:
      c = os.read(ifd, 1)

      # Autocomplete when the callback is set. It returns < 0 when
      # there was an error reading from fd. Otherwise it will return the
      # character that should be handled next.
      if c == _KEY_TAB and self.completion_callback is not None:
        c = ls.complete_line(self.completion_callback)
        if c < 0:
          return str(ls)
        if c == 0:
          continue

      if c == _KEY_ENTER:
        self.history.pop()
        return str(ls)
      elif c == _KEY_BS:
        # backspace: remove the character to the left of the cursor
        ls.edit_backspace()
      elif c == _KEY_ESC:
        # escape sequence
        s0 = os.read(ifd, 1)
        s1 = os.read(ifd, 1)
        if s0 == '[':
          # ESC [ sequence
          if s1 >= '0' and s1 <= '9':
            # Extended escape, read additional byte.
            s2 = os.read(ifd, 1)
            if s2 == '~':
              if s1 == '3':
                # delete
                ls.edit_delete()
          else:
            if s1 == 'A':
              # cursor up
              ls.edit_set(self.history_prev(ls))
            elif s1 == 'B':
              # cursor down
              ls.edit_set(self.history_next(ls))
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
      elif c == _KEY_CTRL_A:
        # go to the start of the line
        ls.edit_move_home()
      elif c == _KEY_CTRL_B:
        # cursor left
        ls.edit_move_left()
      elif c == _KEY_CTRL_C:
        # return None == EOF
        return None
      elif c == _KEY_CTRL_D:
        # delete: remove the character to the right of the cursor.
        # If the line is empty act as an EOF.
        if len(ls.buf):
          ls.edit_delete()
        else:
          self.history.pop()
          return None
      elif c == _KEY_CTRL_E:
        # go to the end of the line
        ls.edit_move_end()
      elif c == _KEY_CTRL_F:
        # cursor right
        ls.edit_move_right()
      elif c == _KEY_CTRL_H:
        # backspace: remove the character to the left of the cursor
        ls.edit_backspace()
      elif c == _KEY_CTRL_K:
        # delete to the end of the line
        ls.delete_to_end()
      elif c == _KEY_CTRL_L:
        # clear screen
        clear_screen()
        ls.refresh_line()
      elif c == _KEY_CTRL_N:
        # next history item
        ls.edit_set(self.history_next(ls))
      elif c == _KEY_CTRL_P:
        # previous history item
        ls.edit_set(self.history_prev(ls))
      elif c == _KEY_CTRL_T:
        # swap current character with the previous
        ls.edit_swap()
      elif c == _KEY_CTRL_U:
        # delete the whole line
        ls.delete_line()
      elif c == _KEY_CTRL_W:
        # delete previous word
        ls.delete_prev_word()
      else:
        # insert the character into the line buffer
        ls.edit_insert(c)

  def read_raw(self, prompt):
    """read a line from stdin in raw mode"""
    if self.enable_rawmode(_STDIN) == -1:
      return None
    s = self.edit(_STDIN, _STDOUT, prompt)
    self.disable_rawmode(_STDIN)
    sys.stdout.write('\r\n')
    return s

  def read(self, prompt):
    """Read a line. Return None on EOF"""
    if not os.isatty(_STDIN):
      # Not a tty. Read from a file/pipe.
      s = sys.stdin.readline().strip('\n')
      return (s, None)[s == '']
    elif unsupported_term():
      # Not a terminal we know about, so basic line reading.
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
    if self.enable_rawmode(_STDIN) != 0:
      return
    cmd = [''] * 4
    while True:
      # get a character
      c = os.read(_STDIN, 1)
      if c == '':
        continue
      # display the character
      if c in string.printable:
        m = {'\r': '\\r', '\n': '\\n', '\t': '\\t'}
        cstr = m.get(c, c)
      else:
        m = {_KEY_ESC: 'ESC'}
        cstr = m.get(c, '?')
      sys.stdout.write("'%s' 0x%02x (%d)\r\n" % (cstr, ord(c), ord(c)))
      sys.stdout.flush()
      # check for quit
      cmd = cmd[1:]
      cmd.append(c)
      if ''.join(cmd) == 'quit':
        break
    # restore the original mode
    self.disable_rawmode(_STDIN)

  def set_completion_callback(self, fn):
    """set the completion callback function"""
    self.completion_callback = fn

  def set_hints_callback(self, fn):
    """set the hints callback function"""
    self.hints_callback = fn

  def set_multiline(self, mode):
    """set multiline mode"""
    self.mlmode = mode

  def history_set(self, idx, line):
    """set a history entry by index number"""
    self.history[len(self.history) - 1 - idx] = line

  def history_get(self, idx):
    """get a history entry by index number"""
    return self.history[len(self.history) - 1 - idx]

  def history_next(self, ls):
    """return next history item"""
    if len(self.history) == 0:
      return None
    # update the current history entry with the line buffer
    self.history_set(ls.history_idx, str(ls))
    ls.history_idx -= 1
    # next history item
    if ls.history_idx < 0:
      ls.history_idx = 0
    return self.history_get(ls.history_idx)

  def history_prev(self, ls):
    """return previous history item"""
    if len(self.history) == 0:
      return None
    # update the current history entry with the line buffer
    self.history_set(ls.history_idx, str(ls))
    ls.history_idx += 1
    # previous history item
    if ls.history_idx >= len(self.history):
      ls.history_idx = len(self.history) - 1
    return self.history_get(ls.history_idx)

  def history_add(self, line):
    """Add a new entry to the history"""
    if self.history_maxlen == 0:
      return
    # don't add duplicate lines
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
    f.write('%s\n' % '\n'.join(self.history))
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



