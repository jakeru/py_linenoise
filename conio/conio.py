"""
Console IO - Python ctype bindings to a modified linenoise library
"""

import ctypes
from ctypes import c_int, c_char_p, c_void_p

import os.path

COMPLETION_CB_FUNC = ctypes.CFUNCTYPE(None, c_char_p, c_void_p)
HELP_CB_FUNC = ctypes.CFUNCTYPE(None, c_char_p)

def readline(prompt):
  ptr = _lib.conio_readline(c_char_p(prompt))
  s = ctypes.cast(ptr, c_char_p)
  line = s.value
  _lib.conio_free(ptr)
  return line

def add_completion(lc, s):
  _lib.conio_add_completion(lc, c_char_p(s))

def completion_cb(buf, lc):
  print('here\n')
  if len(buf) != 0 and buf[0] == 'h':
    add_completion(lc, 'hello')
    add_completion(lc, 'hello there')

def help_cb(buf):
  print('help on "%s"' % buf)

def init():
  ccb = COMPLETION_CB_FUNC(completion_cb)
  hcb = HELP_CB_FUNC(help_cb)
  _lib.conio_init(ccb, hcb)

def key_codes():
  _lib.conio_key_codes()


def _set_func(name, restype, *argtypes):
  getattr(_lib, name).restype = restype
  getattr(_lib, name).argtypes = argtypes

_conio_dir = os.path.dirname(os.path.abspath(__file__))
if os.path.exists(os.path.join(_conio_dir, 'libconio.dll')):
  _lib = ctypes.cdll.LoadLibrary(os.path.join(_conio_dir, 'libconio.dll'))
elif os.path.exists(os.path.join(_conio_dir, 'libconio.so')):
  _lib = ctypes.cdll.LoadLibrary(os.path.join(_conio_dir, 'libconio.so'))
else:
  raise Exception('libconio not found!')

_set_func('conio_init', None, COMPLETION_CB_FUNC, HELP_CB_FUNC)
_set_func('conio_free', None, c_void_p)
_set_func('conio_readline', c_void_p, c_char_p)
_set_func('conio_add_completion', None, c_void_p, c_char_p)
_set_func('conio_key_codes', None)
