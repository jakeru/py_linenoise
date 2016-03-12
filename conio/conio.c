
#include <stdio.h>
#include <stdlib.h>
#include "linenoise.h"

void conio_add_completion(void *lc, const char *str) {
  linenoiseAddCompletion((linenoiseCompletions *)lc, str);
}

void conio_free(void *ptr) {
  free(ptr);
}

void *conio_readline(const char *prompt) {
  return (void *)linenoise(prompt);
}

void conio_key_codes(void) {
  linenoisePrintKeyCodes();
}

void conio_init(linenoiseCompletionCallback *ccb, linenoiseHelpCallback *hcb) {

  printf("%p %p\n", ccb, hcb);

  linenoiseSetCompletionCallback(ccb);
  linenoiseSetHelpCallback(hcb);
}
