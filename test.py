import pexpect
import dataclasses


PROMPT = '\(rr\) '


class RRProcess:
    def __init__(self):
        args = '-o "-ex=set style enabled off"'
        self.rr = pexpect.spawn(f'rr replay --gdb-x yp-gdb.py {args}', timeout=3)
        self.rr.expect('--Type <RET> for more, q to quit, c to continue without paging--')
        self.rr.sendline('')
        self.rr.expect(PROMPT)

    def py_break(self, position):
        self.rr.sendline(f'py-break {position}')
        i = self.rr.expect([f'Breakpoint 1 at 0x[a-z0-9]+: file ../Python/ceval.c, line [0-9]+.', PROMPT])
        assert i == 0

    def cont(self):
        self.rr.sendline(f'cont')
        self.rr.expect(f'Continuing.')
        print('Continuing...')
        
        i = self.rr.expect(['Breakpoint ([0-9]+), _PyEval_EvalFrameDefault \(tstate=[a-z0-9]+,', PROMPT], timeout=30)
        assert i == 0
        self.rr.expect(PROMPT)

    def py_bt(self):
        self.rr.sendline('py-bt')

    def py_next(self):
        self.rr.sendline('py-next')

    def py_rnext(self):
        self.rr.sendline('py-reverse-next')


def main():
    rr = RRProcess()
    rr.py_break('/home/manuel/Projects/yp/test_script.py:main')
    rr.cont()

    rr.py_bt()
    expect = '''Traceback \(most recent call first\):
  File "/home/manuel/Projects/yp/test_script.py", line 13, in main
    def main\(\):
  File "/home/manuel/Projects/yp/test_script.py", line 28, in <module>
    main\(\)'''
    for line in expect.splitlines():
        i = rr.rr.expect([line, PROMPT])
        assert i == 0

    for line in 14, 15:
        rr.py_next()
        rr.rr.expect(f'  File "/home/manuel/Projects/yp/test_script.py", line {line}, in main')
        rr.rr.expect(PROMPT)

    rr.py_rnext()
    rr.rr.expect(f'  File "/home/manuel/Projects/yp/test_script.py", line 14, in main')
    rr.rr.expect(PROMPT)


    print(rr.rr.before.decode())
    rr.rr.interact()


if __name__ == '__main__':
    main()

