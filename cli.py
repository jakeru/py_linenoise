#-----------------------------------------------------------------------------
"""
Command Line Interface

Implements a CLI with:

* hierarchical menus
* command tab completion
* command history
* context sensitive help
* command editing

Notes:

Menu Tuple Format:
(name, descr, submenu) - submenu
(name, descr, leaf) - leaf command with generic <cr> help
(name, descr, leaf, help) - leaf command with specific help

Help Format:
(parm, descr)
"""
#-----------------------------------------------------------------------------

import linenoise

#-----------------------------------------------------------------------------
# common help for cli leaf functions

cr_help = (
  ('<cr>', 'perform the function'),
)

general_help = (
  ('?', 'display command help - Eg. ?, show ?, s?'),
  ('<up>', 'go backwards in command history'),
  ('<dn>', 'go forwards in command history'),
  ('<tab>', 'auto complete commands'),
  ('* note', 'commands can be incomplete - Eg. sh = sho = show'),
)

history_help = (
  ('<cr>', 'display all history'),
  ('<index>', 'recall history entry <index>'),
)

help_fmt = '  %-20s: %s\n'

#-----------------------------------------------------------------------------

def int_arg(ui, arg, limits, base):
  """convert a number string to an integer - or None"""
  try:
    val = int(arg, base)
  except ValueError:
    ui.put(inv_arg)
    return None
  if (val < limits[0]) or (val > limits[1]):
    ui.put(inv_arg)
    return None
  return val

#-----------------------------------------------------------------------------

def display_cols(clist, csize=None):
  """
    return a string for a list of columns
    each element in clist is [col0_str, col1_str, col2_str, ...]
    csize is a list of column width minimums
  """
  if len(clist) == 0:
    return ''
  # how many columns?
  ncols = len(clist[0])
  # make sure we have a well formed csize
  if csize is None:
    csize = [0,] * ncols
  else:
    assert len(csize) == ncols
  # convert any "None" items to ''
  for l in clist:
    assert len(l) == ncols
    for i in range(ncols):
      if l[i] is None:
        l[i] = ''
  # additional column margin
  cmargin = 1
  # go through the strings and bump up csize widths if required
  for l in clist:
    for i in range(ncols):
      if csize[i] <= len(l[i]):
        csize[i] = len(l[i]) + cmargin
  # build the format string
  fmts = []
  for n in csize:
    fmts.append('%%-%ds' % n)
  fmt = ''.join(fmts)
  # generate the string
  s = [(fmt % tuple(l)) for l in clist]
  return '\n'.join(s)

#-----------------------------------------------------------------------------

def split_index(s):
  """split a string on whitespace and return the substring indices"""
  # start and end with whitespace
  ws = True
  s += ' '
  start = []
  end = []
  for (i, c) in enumerate(s):
    if not ws and c == ' ':
      # non-whitespace to whitespace
      end.append(i)
      ws = True
    elif ws and c != ' ':
      # whitespace to non-whitespace
      start.append(i)
      ws = False
  return zip(start, end)

#-----------------------------------------------------------------------------

class cli(object):
  """command line interface"""

  def __init__(self, ui, history=None):
    self.ui = ui
    self.ln = linenoise.linenoise()
    self.ln.set_completion_callback(self.completion_callback)
    self.ln.set_hotkey('?')
    self.ln.history_load(history)
    self.poll = None
    self.root = None
    self.prompt = '> '
    self.running = True

  def set_root(self, root):
    """set the menu root"""
    self.root = root

  def set_prompt(self, prompt):
    """set the command prompt"""
    self.prompt = prompt

  def set_poll(self, poll):
    """set the external polling function"""
    self.poll = poll

  def display_error(self, msg, cmds, idx):
    """display a parse error string"""
    marker = []
    for (i, cmd) in enumerate(cmds):
      l = len(cmd)
      if i == idx:
        marker.append('^' * l)
      else:
        marker.append(' ' * l)
    s = '\n'.join([msg, ' '.join(cmds), ' '.join(marker)])
    self.ui.put('%s\n' % s)

  def display_function_help(self, help_info):
    """display function help"""
    s = []
    for (parm, descr) in help_info:
      if parm is None:
        s.append(['', ''])
      elif descr is None:
        s.append([parm, ''])
      else:
        s.append([parm, ': %s' % descr])
    self.ui.put('%s\n' % display_cols(s, [16, 0]))

  def command_help(self, cmd, menu):
    """display help results for a command at a menu level"""
    for item in menu:
      name = item[0]
      if name.startswith(cmd):
        if isinstance(item[1], tuple):
          # submenu: the next string is the help
          descr = item[2]
        else:
          # command: docstring is the help
          descr = item[1].__doc__
        self.ui.put(help_fmt % (name, descr))

  def function_help(self, item):
    """display help for a leaf function"""
    if len(item) > 2:
      help_info = item[2]
    else:
      help_info = cr_help
    self.display_function_help(help_info)

  def general_help(self):
    """display general help"""
    self.display_function_help(general_help)

  def display_history(self, args):
    """display the command history"""
    # get the history
    h = self.ln.history_list()
    n = len(h)
    if len(args) == 1:
      # retrieve a specific history entry
      idx = int_arg(self.ui, args[0], (0, n - 1), 10)
      if idx is None:
        return
      # Return the next line buffer.
      # Note: linenoise wants to add the line buffer as the zero-th history entry.
      # It can only do this if it's unique- and this isn't because it's a prior
      # history entry. Make it unique by adding a trailing whitespace. The other
      # entries have been stripped prior to being added to history.
      return h[n - idx - 1] + ' '
    else:
      # display all history
      if n:
        s = ['%-3d: %s' % (n - i - 1, l) for (i, l) in enumerate(h)]
        self.ui.put('%s\n' % '\n'.join(s))
      else:
        self.ui.put('no history\n')
      return ''

  @staticmethod
  def completions(line, minlen, cmd, names):
    """return the list of line completions"""
    line += ('', ' ')[cmd == '' and line != '']
    lines = ['%s%s' % (line, x[len(cmd):]) for x in names]
    # pad the lines to a minimum length, we don't want
    # the cursor to move about unecessarily
    return [l + ' ' * max(0, minlen - len(l)) for l in lines]

  def completion_callback(self, cmd_line):
    """return a tuple of line completions for the command line"""
    line = ''
    # split the command line into a list of command indices
    cmd_list = split_index(cmd_line)
    # trace each command through the menu tree
    menu = self.root
    for (start, end) in cmd_list:
      cmd = cmd_line[start:end]
      line = cmd_line[:end]
      # How many items does this token match at this level of the menu?
      matches = [x for x in menu if x[0].startswith(cmd)]
      if len(matches) == 0:
        # no matches, no completions
        return None
      elif len(matches) == 1:
        item = matches[0]
        if len(cmd) < len(item[0]):
          # it's an unambiguous single match, but we still complete it
          return self.completions(line, len(cmd_line), cmd, [item[0],])
        else:
          # we have the whole command - is this a submenu or leaf?
          if isinstance(item[1], tuple):
            # submenu: switch to the submenu and continue parsing
            menu = item[1]
            continue
          else:
            # leaf function: no completions to offer
            return None
      else:
        # Multiple matches at this level. Return the matches.
        return self.completions(line, len(cmd_line), cmd, [x[0] for x in matches])
    # We've made it here without returning a completion list.
    # The prior set of tokens have all matched single submenu items.
    # The completions are all of the items at the current menu level.
    return self.completions(line, len(cmd_line), '', [x[0] for x in menu])

  def parse_cmdline(self, line):
    """
    parse and process the current command line
    return a string for the new command line.
    This is generally '' (empty), but may be non-empty
    if the user needs to edit a pre-entered command.
    """
    # scan the command line into a list of tokens
    cmd_list = [x for x in line.split(' ') if x != '']
    # if there are no commands, print a new empty prompt
    if len(cmd_list) == 0:
      return ''
    # trace each command through the menu tree
    menu = self.root
    for (idx, cmd) in enumerate(cmd_list):
      # A trailing '?' means the user wants help for this command
      if cmd[-1] == '?':
        # strip off the '?'
        cmd = cmd[:-1]
        self.command_help(cmd, menu)
        # strip off the '?' and recycle the command
        return line[:-1]
      # try to match the cmd with a unique menu item
      matches = []
      for item in menu:
        if item[0] == cmd:
          # accept an exact match
          matches = [item]
          break
        if item[0].startswith(cmd):
          matches.append(item)
      if len(matches) == 0:
        # no matches - unknown command
        self.display_error('unknown command', cmd_list, idx)
        # add it to history in case the user wants to edit this junk
        self.ln.history_add(line.strip())
        # go back to an empty prompt
        return ''
      if len(matches) == 1:
        # one match - submenu/leaf
        item = matches[0]
        if isinstance(item[1], tuple):
          # this is a submenu
          # switch to the submenu and continue parsing
          menu = item[1]
          continue
        else:
          # this is a leaf function - get the arguments
          args = cmd_list[idx:]
          del args[0]
          if len(args) != 0:
            if args[-1][-1] == '?':
              self.function_help(item)
              # strip off the '?', repeat the command
              return line[:-1]
          # call the leaf function
          rc = item[1](self.ui, args)
          # post leaf function actions
          if rc is not None:
            # currently only history retrieval returns not None
            # the return code is the next line buffer
            return rc
          else:
            # add the command to history
            self.ln.history_add(line.strip())
            # return to an empty line
            return ''
      else:
        # multiple matches - ambiguous command
        self.display_error('ambiguous command', cmd_list, idx)
        return ''
    # reached the end of the command list with no errors and no leaf function.
    self.ui.put('additional input needed\n')
    return line

  def run(self):
    """get and process cli commands in a loop"""
    line = ''
    while self.running:
      line = self.ln.read(self.prompt, line)
      if line is not None:
        line = self.parse_cmdline(line)
      else:
        # exit: ctrl-C/ctrl-D
        self.running = False
    self.ln.history_save('history.txt')

  def exit(self):
    """exit the cli"""
    self.running = False

#-----------------------------------------------------------------------------
