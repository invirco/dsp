# Off-target tests (host gcc). Run from the PWR folder with `make check`.
HCC    = gcc
HFLAGS = -O1 -Wall -Wextra -g
PY     = python3 ../../../../../tools/pi/d24_pwrlink.py

all: run

link_test: link_test.c sim.h ../link.c ../link.h
	$(HCC) $(HFLAGS) -o $@ link_test.c ../link.c

boot_test: boot_test.c sim.h ../link.c ../bootcmd.c ../bootcmd.h ../proto.h
	$(HCC) $(HFLAGS) -o $@ boot_test.c ../link.c ../bootcmd.c

p1_test: p1_test.c ../p1.c ../p1.h ../config.h
	$(HCC) $(HFLAGS) -o $@ p1_test.c ../p1.c -lm

run: link_test boot_test p1_test
	./link_test
	./boot_test ../pwr-mcu.img
	./p1_test
	# host tool <-> firmware link, both directions
	./link_test emit c_line.txt
	$(PY) --decode-line c_line.txt
	$(PY) --emit-line py_line.txt
	./link_test decode py_line.txt
	$(PY) --selftest

clean:
	rm -f link_test boot_test p1_test c_line.txt py_line.txt

.PHONY: all run clean
