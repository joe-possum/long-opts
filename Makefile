auto : main.c auto.c
	gcc -Wall -o $@ $^

auto.c : parse-opt.py opt.ascii
	python3 $^
