import pexpect

TEST1 = ('''
--Type <RET> for more, q to quit, c to continue without paging--
<<
(rr)
<< py-break /home/manuel/Projects/yp/test_script.py:main
Breakpoint 1 at 0x\([0-9a-f]+\): file ../Python/ceval.c, line 1324.
<< cont
Continuing.
Traceback (most recent call first):
  File "/home/manuel/Projects/yp/test_script.py", line 13, in main
    def main():
  File "/home/manuel/Projects/yp/test_script.py", line 28, in <module>
    main()
<< py-step
Traceback (most recent call first):
  File "/home/manuel/Projects/yp/test_script.py", line 14, in main
    y = 2      # 1
  File "/home/manuel/Projects/yp/test_script.py", line 28, in <module>
    main()
<< py-step
Traceback (most recent call first):
  File "/home/manuel/Projects/yp/test_script.py", line 15, in main
    y = y \+ 1  # 2
  File "/home/manuel/Projects/yp/test_script.py", line 28, in <module>
    main()
<< py-reverse-step
Traceback (most recent call first):
  File "/home/manuel/Projects/yp/test_script.py", line 14, in main
    y = 2      # 1
  File "/home/manuel/Projects/yp/test_script.py", line 28, in <module>
    main()
<< py-reverse-step
Traceback (most recent call first):
  File "/home/manuel/Projects/yp/test_script.py", line 13, in main
    def main():
  File "/home/manuel/Projects/yp/test_script.py", line 28, in <module>
    main()
<< py-reverse-step
Traceback (most recent call first):
  File "/home/manuel/Projects/yp/test_script.py", line 13, in main
    def main():
  File "/home/manuel/Projects/yp/test_script.py", line 28, in <module>
    main()
<< py-step
Traceback (most recent call first):
  File "/home/manuel/Projects/yp/test_script.py", line 13, in main
    def main():
  File "/home/manuel/Projects/yp/test_script.py", line 28, in <module>
    main()
<< py-step
Traceback (most recent call first):
  File "/home/manuel/Projects/yp/test_script.py", line 14, in main
    y = 2      # 1
  File "/home/manuel/Projects/yp/test_script.py", line 28, in <module>
    main()
(rr) 
<< py-step
Traceback (most recent call first):
  File "/home/manuel/Projects/yp/test_script.py", line 15, in main
    y = y \+ 1  # 2
  File "/home/manuel/Projects/yp/test_script.py", line 28, in <module>
    main()
<< py-step
Traceback (most recent call first):
  File "/home/manuel/Projects/yp/test_script.py", line 16, in main
    print(0)   # 3
  File "/home/manuel/Projects/yp/test_script.py", line 28, in <module>
    main()
<< py-step
Traceback (most recent call first):
  File "/home/manuel/Projects/yp/test_script.py", line 17, in main
    y = y \+ 2  # 4
  File "/home/manuel/Projects/yp/test_script.py", line 28, in <module>
    main()
'''.strip()
         .replace('\(', '++[[').replace('\)', ']]++')
         .replace('(', '\(').replace(')', '\)')
         .replace('++[[', '(').replace(']]++', ')')
         )


def run_test(instructions):
    args = '-o "-ex=set style enabled off"'
    rr = pexpect.spawn(f'yp replay {args}', timeout=3)
    for line in instructions.splitlines():
        try:
            if line.startswith('<<'):
                print(line)
                j = 1 if len(line) > 2 and line[2] == ' ' else 0
                rr.sendline(line[2 + j:])
            else:
                if rr.before and len(rr.before.strip()) > 0:
                    print(rr.before.decode().strip())
                print(f'??? {line}')
                rr.expect(line, timeout=10)
        except Exception:
            print('  -- EXCEPTION --')
            print('  >> OUTPUT >>')
            print(rr.buffer.decode())
            print('  << OUTPUT <<')
            raise
    print('<<< TEST DONE >>>')


if __name__ == '__main__':
    run_test(TEST1)
