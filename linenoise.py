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
import select
import atexit
import termios
import struct
import fcntl
import string
import logging
import enum

# -----------------------------------------------------------------------------
# logging

_debug_mode = False
if _debug_mode:
    logging.basicConfig(
        filename="linenoise_debug.log", format="%(asctime)s %(message)s", datefmt="%Y%m%d %I:%M:%S", level=logging.DEBUG
    )

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

_CHAR_TIMEOUT = 0.02  # 20 ms


def _getc(fd, timeout=-1):
    """
    read a single character string from a file (with timeout)
    timeout = 0 : return immediately
    timeout < 0 : wait for the character (block)
    timeout > 0 : wait for timeout seconds
    """
    # use select() for the timeout
    if timeout >= 0:
        (rd, _, _) = select.select((fd,), (), (), timeout)
        if len(rd) == 0:
            return _KEY_NULL
    # read the character
    c = os.read(fd, 1)
    if c == "":
        return _KEY_NULL
    return c.decode("utf8")


def _puts(fd, s):
    return os.write(fd, s.encode("utf8"))


def would_block(fd, timeout):
    """if fd is not readable within timeout seconds - return True"""
    (rd, _, _) = select.select((fd,), (), (), timeout)
    return len(rd) == 0


# -----------------------------------------------------------------------------

# Use this value if we can't work out how many columns the terminal has.
_DEFAULT_COLS = 80


class EditResult(enum.Enum):
    """Result codes for a few edit functions"""

    EOF_OR_ERROR = -1
    MORE = 0
    ENTER = 1
    HOTKEY = 2
    ESCAPE = 3


def get_cursor_position(ifd, ofd):
    """Get the horizontal cursor position"""
    # query the cursor location
    if _puts(ofd, "\x1b[6n") != 4:
        return -1
    # read the response: ESC [ rows ; cols R
    # rows/cols are decimal number strings
    buf = []
    while len(buf) < 32:
        c = _getc(ifd, _CHAR_TIMEOUT)
        if c == _KEY_NULL:
            break
        buf.append(c)
        if buf[-1] == "R":
            break
    # parse it: esc [ number ; number R (at least 6 characters)
    if len(buf) < 6 or buf[0] != _KEY_ESC or buf[1] != "[" or buf[-1] != "R":
        return -1
    # should have 2 number fields
    x = "".join(buf[2:-1]).split(";")
    if len(x) != 2:
        return -1
    (_, cols) = x
    # return the cols
    return int(cols, 10)


def get_columns(ifd, ofd):
    """Get the number of columns for the terminal. Assume _DEFAULT_COLS if it fails."""
    cols = 0
    # try using the ioctl to get the number of cols
    try:
        t = fcntl.ioctl(_STDOUT, termios.TIOCGWINSZ, struct.pack("HHHH", 0, 0, 0, 0))
        (_, cols, _, _) = struct.unpack("HHHH", t)
    except:
        pass
    if cols == 0:
        # the ioctl failed - try using the terminal itself
        start = get_cursor_position(ifd, ofd)
        if start < 0:
            return _DEFAULT_COLS
        # Go to right margin and get position
        if _puts(ofd, "\x1b[999C") != 6:
            return _DEFAULT_COLS
        cols = get_cursor_position(ifd, ofd)
        if cols < 0:
            return _DEFAULT_COLS
        # restore the position
        if cols > start:
            _puts(ofd, "\x1b[%dD" % (cols - start))
    return cols


# -----------------------------------------------------------------------------


def clear_screen():
    """Clear the screen"""
    sys.stdout.write("\x1b[H\x1b[2J")
    sys.stdout.flush()


def beep():
    """Beep"""
    sys.stderr.write("\x07")
    sys.stderr.flush()


# -----------------------------------------------------------------------------


def unsupported_term():
    """return True if we know we don't support this terminal"""
    unsupported = ("dumb", "cons25", "emacs")
    term = os.environ.get("TERM", "")
    return term in unsupported


# -----------------------------------------------------------------------------


class line_state:
    """line editing state"""

    def __init__(self, ifd, ofd, prompt, ts):
        self.ifd = ifd  # stdin file descriptor
        self.ofd = ofd  # stdout file descriptor
        self.prompt = prompt  # prompt string
        self.ts = ts  # terminal state
        self.history_idx = 0  # history index we are currently editing, 0 is the LAST entry
        self.buf = []  # line buffer
        self.cols = get_columns(ifd, ofd)  # number of columns in terminal
        self.pos = 0  # current cursor position within line buffer
        self.oldpos = 0  # previous refresh cursor position (multiline)
        self.maxrows = 0  # maximum num of rows used so far (multiline)

    def refresh_show_hints(self):
        """show hints to the right of the cursor"""
        if self.ts.hints_callback is None:
            # no hints
            return []
        if len(self.prompt) + len(self.buf) >= self.cols:
            # no space to display hints
            return []
        # get the hint
        result = self.ts.hints_callback(str(self))
        if result is None:
            # no hints
            return []
        (hint, color, bold) = result
        if hint is None or len(hint) == 0:
            # no hints
            return []
        # work out the hint length
        hlen = min(len(hint), self.cols - len(self.prompt) - len(self.buf))
        seq = []
        if bold and color < 0:
            color = 37
        if color >= 0 or bold:
            seq.append("\033[%d;%d;49m" % ((0, 1)[bold], color))
        seq.append(hint[:hlen])
        if color >= 0 or bold:
            seq.append("\033[0m")
        return seq

    def refresh_singleline(self, *, clear, write):
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
        if clear:
            # cursor to the left edge
            seq.append("\r")
        if write:
            # write the prompt
            seq.append(self.prompt)
            # write the current buffer content
            seq.append("".join([self.buf[i] for i in range(idx, idx + blen)]))
            # Show hints (if any)
            seq.extend(self.refresh_show_hints())
        if clear:
            # Erase to right
            seq.append("\x1b[0K")
        if write:
            # Move cursor to original position
            seq.append("\r\x1b[%dC" % (plen + pos))
        # write it out
        _puts(self.ofd, "".join(seq))

    def refresh_multiline(self, *, clear, write):
        """multiline refresh"""
        plen = len(self.prompt)
        # cursor position relative to row
        rpos = (plen + self.oldpos + self.cols) // self.cols
        # rows used by current buf
        rows = (plen + len(self.buf) + self.cols - 1) // self.cols
        seq = []
        if clear:
            # First step: clear all the lines used before. To do so start by going to the last row.
            old_rows = self.maxrows
            if old_rows - rpos > 0:
                logging.debug("go down %d" % (old_rows - rpos))
                seq.append("\x1b[%dB" % (old_rows - rpos))
            # Now for every row clear it, go up.
            for _ in range(old_rows - 1):
                logging.debug("clear+up")
                seq.append("\r\x1b[0K\x1b[1A")
            # Clear the top line.
            logging.debug("clear")
            seq.append("\r\x1b[0K")
        if write:
            # Write the prompt and the current buffer content
            seq.append(self.prompt)
            seq.append(str(self))
            self.maxrows = rows
            # Show hints (if any)
            seq.extend(self.refresh_show_hints())
            # If we are at the very end of the screen with our cursor, we need to
            # emit a newline and move the cursor to the first column.
            if self.pos and self.pos == len(self.buf) and (self.pos + plen) % self.cols == 0:
                logging.debug("<newline>")
                seq.append("\n\r")
                rows += 1
                if rows > self.maxrows:
                    self.maxrows = rows
            # Move cursor to right position.
            rpos2 = (plen + self.pos + self.cols) // self.cols  # current cursor relative row.
            logging.debug("rpos2 %d" % rpos2)
            # Go up till we reach the expected position.
            if rows - rpos2 > 0:
                logging.debug("go-up %d" % (rows - rpos2))
                seq.append("\x1b[%dA" % (rows - rpos2))
            # Set column
            col = (plen + self.pos) % self.cols
            logging.debug("set col %d" % (1 + col))
            if col:
                seq.append("\r\x1b[%dC" % col)
            else:
                seq.append("\r")
        logging.debug("\n")
        # save the cursor position
        self.oldpos = self.pos
        # write it out
        _puts(self.ofd, "".join(seq))

    def refresh_line(self, clear=True):
        """refresh the edit line"""
        if self.ts.mlmode:
            self.refresh_multiline(clear=clear, write=True)
        else:
            self.refresh_singleline(clear=clear, write=True)

    def hide(self):
        """hide the edit line"""
        if self.ts.mlmode:
            self.refresh_multiline(clear=True, write=False)
        else:
            self.refresh_singleline(clear=True, write=False)
        self.ts.disable_rawmode(self.ifd)

    def show(self):
        """show the edit line"""
        res = self.ts.enable_rawmode(self.ifd)
        if res != 0:
            return res
        if self.ts.mlmode:
            self.refresh_multiline(clear=False, write=True)
        else:
            self.refresh_singleline(clear=False, write=True)
        return 0

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

    def edit_set(self, s, pos = None):
        """set the line buffer to a string"""
        if s is None:
            return
        self.buf = list(s)
        self.pos = len(self.buf) if pos is None else pos
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

    def edit_move_word_left(self):
        """move to the beginning of current or previous word"""
        pos = self.pos
        while pos > 0 and self.buf[pos-1].isspace():
            pos -= 1
        while pos > 0 and not self.buf[pos-1].isspace():
            pos -= 1
        if pos != self.pos:
            self.pos = pos
            self.refresh_line()


    def edit_move_word_right(self):
        """move to the beginning of next word"""
        pos = self.pos
        while pos < len(self.buf) and not self.buf[pos].isspace():
            pos += 1
        while pos < len(self.buf) and self.buf[pos].isspace():
            pos += 1
        if pos != self.pos:
            self.pos = pos
            self.refresh_line()

    def delete_line(self):
        """delete the line"""
        self.buf = []
        self.pos = 0
        self.refresh_line()

    def delete_to_end(self):
        """delete from the current cursor postion to the end of the line"""
        self.buf = self.buf[: self.pos]
        self.refresh_line()

    def delete_prev_word(self):
        """delete the previous space delimited word"""
        old_pos = self.pos
        # remove spaces
        while self.pos > 0 and self.buf[self.pos - 1] == " ":
            self.pos -= 1
        # remove word
        while self.pos > 0 and self.buf[self.pos - 1] != " ":
            self.pos -= 1
        self.buf = self.buf[: self.pos] + self.buf[old_pos:]
        self.refresh_line()

    def complete_line(self):
        """show completions for the current line"""
        c = _KEY_NULL
        # get a list of line completions
        lc = self.ts.completion_callback(str(self))
        if lc is None or len(lc) == 0:
            # no line completions
            beep()
        else:
            # navigate and display the line completions
            stop = False
            idx = 0
            while not stop:
                if idx < len(lc):
                    # save the line buffer
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
                c = _getc(self.ifd)
                if c == _KEY_NULL:
                    # error on read
                    stop = True
                elif c == _KEY_TAB:
                    # loop through the completions
                    idx = (idx + 1) % (len(lc) + 1)
                    if idx == len(lc):
                        beep()
                elif c == _KEY_ESC:
                    # could be an escape, could be an escape sequence
                    if would_block(self.ifd, _CHAR_TIMEOUT):
                        # nothing more to read, looks like a single escape
                        # re-show the original buffer
                        if idx < len(lc):
                            self.refresh_line()
                        # don't pass the escape key back
                        c = _KEY_NULL
                    else:
                        # probably an escape sequence
                        # update the buffer and return
                        if idx < len(lc):
                            self.buf = list(lc[idx])
                            self.pos = len(self.buf)
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
        return "".join(self.buf)


# -----------------------------------------------------------------------------

# Indices within the termios array
_C_IFLAG = 0
_C_OFLAG = 1
_C_CFLAG = 2
_C_LFLAG = 3
_C_CC = 6


class linenoise:
    """terminal state"""

    def __init__(self):
        self.history = []  # list of history strings
        self.history_maxlen = 32  # maximum number of history entries (default)
        self.rawmode = False  # are we in raw mode?
        self.mlmode = False  # are we in multiline mode?
        self.atexit_flag = False  # have we registered a cleanup upon exit function?
        self.orig_termios = None  # saved termios attributes
        self.completion_callback = None  # callback function for tab completion
        self.hints_callback = None  # callback function for hints
        self.hotkey = None  # character for hotkey

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
        raw[_C_IFLAG] &= ~(termios.BRKINT | termios.ICRNL | termios.INPCK | termios.ISTRIP | termios.IXON)
        # output modes - disable post processing
        raw[_C_OFLAG] &= ~(termios.OPOST)
        # control modes - set 8 bit chars
        raw[_C_CFLAG] |= termios.CS8
        # local modes - echo off, canonical off, no extended functions, no signal chars (^Z,^C)
        raw[_C_LFLAG] &= ~(termios.ECHO | termios.ICANON | termios.IEXTEN | termios.ISIG)
        # control chars - set return condition: min number of bytes and timer.
        # We want read to return every single byte, without timeout.
        raw[_C_CC][termios.VMIN] = 1
        raw[_C_CC][termios.VTIME] = 0
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
        sys.stdout.write("\r")
        sys.stdout.flush()
        self.disable_rawmode(_STDIN)

    def edit_start(self, prompt, s="", ifd=_STDIN, ofd=_STDOUT):
        """
        Initiate a non-blocking read operation.
        Call `edit_feed()` whenever data is available on file descriptor `ifd`.
        Call `edit_stop()` to stop the read operation.
        Returns a `line_state` object on success and `None` on error.
        """
        if self.enable_rawmode(ifd) != 0:
            return None
        # create the line state
        ls = line_state(ifd, ofd, prompt, self)
        # set and output the initial line
        ls.edit_set(s)
        # The latest history entry is always our current buffer
        self.history_add(str(ls))
        return ls

    def edit_feed(self, ls):
        """
        Process input data during a non-blocking read operation.
        This function should be called whenever data is available on the file
        descriptor `ls.ifd`.
        The function `edit_start()` should be called before this in order to
        initiate a non-blocking read operation.
        Returns the result of the operation as an `EditResult` enum.
        If `EditResult.MORE` is returned, this function should be called again
        whenever there is data available.
        If anything else is returned, the function `edit_stop()` should be
        called.
        """
        if ls:
            ifd = ls.ifd
            c = _getc(ifd)
            if c == _KEY_NULL:
                # error on read
                return EditResult.EOF_OR_ERROR
            # Autocomplete when the callback is set.
            # It returns the character that should be handled next.
            if c == _KEY_TAB and self.completion_callback is not None:
                c = ls.complete_line()
                if c == _KEY_NULL:
                    return EditResult.MORE
            # handle the key code
            if c == _KEY_ENTER or c == self.hotkey:
                self.history.pop()
                if self.hints_callback:
                    # Refresh the line without hints to leave the
                    # line as the user typed it after the newline.
                    hcb = self.hints_callback
                    self.hints_callback = None
                    ls.refresh_line()
                    self.hints_callback = hcb
                return EditResult.ENTER if c == _KEY_ENTER else EditResult.HOTKEY
            elif c == _KEY_BS:
                # backspace: remove the character to the left of the cursor
                ls.edit_backspace()
            elif c == _KEY_ESC:
                if would_block(ifd, _CHAR_TIMEOUT):
                    # looks like a single escape- abandon the line
                    self.history.pop()
                    return EditResult.ESCAPE
                # escape sequence
                s0 = _getc(ifd, _CHAR_TIMEOUT)
                s1 = _getc(ifd, _CHAR_TIMEOUT)
                if s0 == "[":
                    # ESC [ sequence
                    if s1 >= "0" and s1 <= "9":
                        # Extended escape, read additional byte.
                        s2 = _getc(ifd, _CHAR_TIMEOUT)
                        if s2 == "~":
                            if s1 == "3":
                                # delete
                                ls.edit_delete()
                        elif s2 == ";":
                            s3 = _getc(ifd, _CHAR_TIMEOUT)
                            s4 = _getc(ifd, _CHAR_TIMEOUT)
                            if s3 == "5":
                                if s4 == "C":
                                     # ctrl + right
                                     ls.edit_move_word_right()
                                elif s4 == "D":
                                     # ctrl + left
                                     ls.edit_move_word_left()

                    else:
                        if s1 == "A":
                            # cursor up
                            self.history_prev(ls)
                        elif s1 == "B":
                            # cursor down
                            self.history_next(ls)
                        elif s1 == "C":
                            # cursor right
                            ls.edit_move_right()
                        elif s1 == "D":
                            # cursor left
                            ls.edit_move_left()
                        elif s1 == "H":
                            # cursor home
                            ls.edit_move_home()
                        elif s1 == "F":
                            # cursor end
                            ls.edit_move_end()
                elif s0 == "0":
                    # ESC 0 sequence
                    if s1 == "H":
                        # cursor home
                        ls.edit_move_home()
                    elif s1 == "F":
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
                return EditResult.EOF_OR_ERROR
            elif c == _KEY_CTRL_D:
                # delete: remove the character to the right of the cursor.
                # If the line is empty act as an EOF.
                if len(ls.buf) != 0:
                    ls.edit_delete()
                else:
                    self.history.pop()
                    return EditResult.EOF_OR_ERROR
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
                self.history_next(ls)
            elif c == _KEY_CTRL_P:
                # previous history item
                self.history_prev(ls)
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
            return EditResult.MORE
        else:
            return EditResult.EOF_OR_ERROR

    def edit_stop(self, ls):
        """
        Stops a non-blocking read operation.
        This function should always be called (at some point) after a call to
        `edit_start()` has been made.
        Note that it is also possible to temporarily hide and show the command
        line using the functions `ls.hide()` and `ls.show()`.
        """
        self.disable_rawmode(ls.ifd)
        sys.stdout.write("\r\n")

    def edit_blocking(self, prompt, s, ifd, ofd):
        """
        Perform a blocking read.
        This function can only be used if the file descriptor `ifd` is a
        supported tty.
        The function `read()` can be used instead to get a fallback for
        unsupported ttys.
        Returns the result (see `EditResult`) as well as the command line
        state (see `line_state`, `None` on error).
        """
        ls = self.edit_start(prompt, s, ifd, ofd)
        if not ls:
            return EditResult.EOF_OR_ERROR, None
        while (res := self.edit_feed(ls)) == EditResult.MORE:
            pass
        self.edit_stop(ls)
        return res, ls

    def read_raw(self, prompt, s):
        """read a line from stdin in raw mode"""
        res, ls = self.edit_blocking(prompt, s, _STDIN, _STDOUT)
        if res == EditResult.ENTER:
            return str(ls)
        elif res == EditResult.HOTKEY:
            return str(ls) + (self.hotkey if self.hotkey else "")
        elif res == EditResult.ESCAPE:
            return ""
        elif res == EditResult.EOF_OR_ERROR:
            return None
        else:
            raise ValueError(res)

    def read(self, prompt, s=""):
        """Read a line. Return None on EOF"""
        if not os.isatty(_STDIN):
            # Not a tty. Read from a file/pipe.
            s = sys.stdin.readline().strip("\n")
            return (s, None)[s == ""]
        if unsupported_term():
            # Not a terminal we know about, so basic line reading.
            try:
                s = input(prompt)
            except EOFError:
                s = None
            return s
        return self.read_raw(prompt, s)

    def loop(self, fn, exit_key=_KEY_CTRL_D):
        """
        Call the provided function in a loop.
        Exit when the function returns True or when the exit key is pressed.
        Returns True when the loop function completes, False for early exit.
        """
        if self.enable_rawmode(_STDIN) == -1:
            return
        rc = None
        while True:
            if fn():
                # the loop function has completed
                rc = True
                break
            if _getc(_STDIN, timeout=0.01) == exit_key:
                # the loop has been cancelled
                rc = False
                break
        self.disable_rawmode(_STDIN)
        return rc

    def print_keycodes(self):
        """Print scan codes on screen for debugging/development purposes"""
        print("Linenoise key codes debugging mode.")
        print("Press keys to see scan codes. Type 'quit' at any time to exit.")
        if self.enable_rawmode(_STDIN) != 0:
            return
        cmd = [""] * 4
        while True:
            # get a character
            c = _getc(_STDIN)
            if c == _KEY_NULL:
                continue
            # display the character
            if c in string.printable:
                m = {"\r": "\\r", "\n": "\\n", "\t": "\\t"}
                cstr = m.get(c, c)
            else:
                m = {_KEY_ESC: "ESC"}
                cstr = m.get(c, "?")
            sys.stdout.write("'%s' 0x%02x (%d)\r\n" % (cstr, ord(c), ord(c)))
            sys.stdout.flush()
            # check for quit
            cmd = cmd[1:]
            cmd.append(c)
            if "".join(cmd) == "quit":
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

    def set_hotkey(self, key):
        """
        Set the hotkey. A hotkey will cause line editing to exit.
        The hotkey will be appended to the line buffer but not displayed.
        """
        self.hotkey = key

    def history_set(self, idx, line):
        """set a history entry by index number"""
        self.history[len(self.history) - 1 - idx] = line

    def history_get(self, idx):
        """get a history entry by index number"""
        return self.history[len(self.history) - 1 - idx]

    def history_list(self):
        """return the full history list"""
        return self.history

    def history_next(self, ls):
        """Show next history item"""
        if len(self.history) == 0:
            return None
        # update the current history entry with the line buffer
        self.history_set(ls.history_idx, str(ls))
        ls.history_idx -= 1
        # next history item
        if ls.history_idx < 0:
            ls.history_idx = 0
        ls.edit_set(self.history_get(ls.history_idx))

    def history_prev(self, ls):
        """Show previous history item"""
        if len(self.history) == 0:
            return None
        # update the current history entry with the line buffer
        self.history_set(ls.history_idx, str(ls))
        ls.history_idx += 1
        # previous history item
        if ls.history_idx >= len(self.history):
            ls.history_idx = len(self.history) - 1
        ls.edit_set(self.history_get(ls.history_idx))

    def history_add(self, line):
        """Add a new entry to the history"""
        if self.history_maxlen == 0:
            return
        # don't re-add the last entry
        if len(self.history) != 0 and line == self.history[-1]:
            return
        if len(self.history) == self.history_maxlen:
            # remove the first entry
            self.history.pop(0)
        # add the line to the history
        self.history.append(line)

    def history_set_maxlen(self, n):
        """Set the maximum length for the history. Truncate the current history if needed."""
        if n < 0:
            return
        self.history_maxlen = n
        current_length = len(self.history)
        if current_length > self.history_maxlen:
            # truncate and retain the latest history
            self.history = self.history[current_length - self.history_maxlen :]

    def history_save(self, fname):
        """Save the history to a file"""
        old_umask = os.umask(stat.S_IXUSR | stat.S_IRWXG | stat.S_IRWXO)
        f = open(fname, "w")
        os.umask(old_umask)
        os.chmod(fname, stat.S_IRUSR | stat.S_IWUSR)
        f.write("%s\n" % "\n".join(self.history))
        f.close()

    def history_load(self, fname):
        """Load history from a file"""
        self.history = []
        if fname and os.path.isfile(fname):
            f = open(fname, "r")
            x = f.readlines()
            f.close()
            self.history = [l.strip() for l in x]


# -----------------------------------------------------------------------------
