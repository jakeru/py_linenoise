# py_linenoise

A port of linenoise to Python (because sometimes readline doesn't cut it...)

See: http://github.com/antirez/linenoise

## Standard Features
 * Single line editing
 * Multiline editing
 * Input from files/pipes
 * Input from unsupported terminals
 * History
 * Completions
 * Hints

## Other Features
 * Line buffer initialization: Set an initial buffer string for editing.
 * Hot keys: Set a special hot key for exiting line editing.
 * Loop Functions: Call a function in a loop until an exit key is pressed.
 
## Motiviation

 * How do you have a hot key exit the line editing so you can offer context sensitive help?
 * How do you call a polling function during line editing so you can check for other things?

These things might be possible in C but the Python readline packaging makes it difficult.
Having a simple/native Python implementation of line editing makes these things much easier. 
