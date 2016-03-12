PKG = linenoise-master

SRC = $(PKG)/linenoise.c \
      conio.c \

PATCHFILES = $(sort $(wildcard *.patch))

PATCH_CMD = \
  for f in $(PATCHFILES); do\
    echo $$f; \
    patch -s -d $(PKG) -p1 -b -z .original < $$f; \
  done

OBJ = $(SRC:.c=.o)

CFLAGS = -Wall -Wextra -Wstrict-prototypes -Werror
CFLAGS += -O2 -fPIC
CFLAGS += -I $(PKG)

%.o: %.c
	$(CC) $(CFLAGS) -o $@ -c $^

%.so: $(OBJ)
	$(CC) -shared $(CFLAGS) -o $@ $^

OUT = libconio.so

all: extract $(OBJ) $(OUT)

extract:
	tar jxvf $(PKG).tar.bz2
	$(PATCH_CMD)  

clean:
	-rm -rf $(PKG)
	-rm -f $(OUT)
	-rm -f $(OBJ)
	-rm -f *.pyc
