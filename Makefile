cmdline : main.c cmdline.c
	gcc -Wall -o $@ $^

cmdline.c cmdline.h : parse-opt.py opt.ascii
	python3 $^
