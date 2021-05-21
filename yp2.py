#!/usr/bin/env python3

import re
import sys
from pathlib import Path
from pygdbmi.gdbcontroller import GdbController
from pprint import pprint


class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class RRController(GdbController):
    def breakpoint(self, arg: str, **kwargs) -> int:
        while True:
            responses = self.write(f'break {arg}', **kwargs)
            r = next(r['payload']['bkpt'] for r in responses if r['message'] == 'breakpoint-created')
            r['number'] = int(r['number'])
            return r

    def cont(self, timeout_sec=10):
        responses = self.write('continue', timeout_sec=timeout_sec)
        return responses

    def where(self, timeout_sec=10):
        responses = self.write('where', timeout_sec=timeout_sec)
        pprint(responses)
        print()



def init_frame(rr):
    res = rr.write(f'-data-evaluate-expression co', timeout_sec=1)
    assert res[0]['message'] == 'done', f'co failed: {res!r}'
    code = res[0]['payload']['value']
    code = int(code, base=16)

    res = rr.write(f'-data-evaluate-expression first_instr', timeout_sec=1)
    assert res[0]['message'] == 'done', f'first_instr failed: {res!r}'
    first_instr = res[0]['payload']['value']
    first_instr = int(first_instr, base=16)

    res = rr.write(f'-data-evaluate-expression co.co_filename', timeout_sec=1)
    assert res[0]['message'] == 'done', f'f.f_code.f_filename failed: {res!r}'
    filename = res[0]['payload']['value']

    res = rr.write(f'-data-evaluate-expression co.co_name', timeout_sec=1)
    assert res[0]['message'] == 'done', f'f.f_code.f_name failed: {res!r}'
    name = res[0]['payload']['value']

    return code, first_instr, filename, name


def get_next_instr(rr):
    res = rr.write(f'-data-evaluate-expression next_instr', timeout_sec=1)
    assert res[0]['message'] == 'done', f'next_instr failed: {res!r}'
    next_instr = res[0]['payload']['value']
    next_instr = int(next_instr, base=16)
    return next_instr


def get_lineno(rr, code, f_lasti):
    bounds = alloc_bounds(rr)

    cmd = f'call _PyCode_CheckLineNumber({code}, {f_lasti}, {bounds})'
    res = rr.write(cmd, timeout_sec=1)
#    pprint(res)
    payload = res[1]['payload']
    _, payload = payload.split('=')
    payload = payload.strip(' \\n')
    lineno = int(payload)

    res = rr.write(f'print ((PyAddrPair *) {bounds}).ap_lower', timeout_sec=1)
#    pprint(res)
    payload = res[1]['payload']
    _, payload = payload.split('=')
    payload = payload.strip(' \\n')
    instr_lb = int(payload)

    res = rr.write(f'print ((PyAddrPair *) {bounds}).ap_upper', timeout_sec=1)
#    pprint(res)
    payload = res[1]['payload']
    _, payload = payload.split('=')
    payload = payload.strip(' \\n')
    instr_ub = int(payload)

    free_bounds(rr, bounds)

    return lineno, instr_lb, instr_ub


def alloc_bounds(rr):
    res = rr.write(f'-data-evaluate-expression malloc(sizeof(PyAddrPair))', timeout_sec=1)
    assert res[0]['message'] == 'done', res
    bounds = res[0]['payload']['value']

    res = rr.write(f'call memset({bounds}, 0, sizeof(PyAddrPair))', timeout_sec=1)
    assert any(r['message'] == 'done' for r in res), res
    return bounds


def free_bounds(rr, bounds):
    res = rr.write(f'-data-evaluate-expression free({bounds})', timeout_sec=1)
    assert res[0]['message'] == 'done', res


def ceval_dispatch_lines():
    contents = Path('/tmp/ceval.c').read_text().splitlines()
    lines = [l for i, l in enumerate(contents)]
#    lines = [i + 1 for i, l in enumerate(contents) if re.search(r'DISPATCH\(\)\;$', l)]
    lines = [i + 1 + 1 for i, l in enumerate(contents) if r'case TARGET(' in l]
    assert len(lines) > 0
    return lines


DISPATCH_LIST = [f'../Python/ceval.c:{lineno}' for lineno in ceval_dispatch_lines()]

INIT_FRAME = '../Python/ceval.c:1324'
FAST_NEXT_OPCODE = '../Python/ceval.c:1407'
END_FRAME = '../Python/ceval.c:3844'


def py_string(obj):
    return f'((char *) (((PyASCIIObject *) {obj}) + 1))'


def main():
    command = ['rr', 'replay', '-o', '--interpreter=mi3']
    rr = RRController(command=command)

    res = None
    while res is None or all(r['message'] != 'stopped' for r in res):
        res = rr.get_gdb_response(timeout_sec=1, raise_error_on_timeout=False)
        pprint(res)
    
    encode_c = lambda s: s
    filename = encode_c('test_script.py')

    where = f'$_streq("/home/manuel/Projects/yp/test_script.py", {py_string("co.co_filename")})'
    where += f' && $_streq("main", {py_string("co.co_name")})'

    cmds = [
        f'break {INIT_FRAME} if {where}',
#        f'break {FAST_NEXT_OPCODE}',
        f'break {INIT_FRAME}',
        f'break {END_FRAME}',
    ]
    cmds += [f'break {line}' for line in DISPATCH_LIST]
    print(cmds)
    res = rr.write(cmds, timeout_sec=10)

    brk_ids = {}
    brk_ids[INIT_FRAME] = 2
    brk_ids[END_FRAME] = 3
    DISPATCH_BRK_ID_START = brk_ids[END_FRAME] + 1
    dispatch_brk_ids = {line: DISPATCH_BRK_ID_START + i for i, line in enumerate(DISPATCH_LIST)}
    brk_ids.update(dispatch_brk_ids)

    cmds = [    
        f'disable {brk_ids[INIT_FRAME]}',
        f'disable {brk_ids[END_FRAME]}',
    ]
    cmds += [f'disable {brk_ids[line]}' for line in DISPATCH_LIST]

    res = rr.write(cmds, timeout_sec=10)

    print('START: -+' * 40)
    code = []
    first_instr = []
    filename = []
    name = []
    instr_lb = []
    instr_ub = []
    instr_prev = []
    next_instr = [-1]

    while True:
        print(bcolors.OKGREEN + 'continue...' + bcolors.ENDC)
        res = rr.write(f'-exec-continue', timeout_sec=100)
        while all(r['message'] != 'stopped' for r in res):
            res += rr.get_gdb_response(timeout_sec=1, raise_error_on_timeout=False)
            #pprint(res)

        try:
            r = next(r for r in res if r['message'] == 'breakpoint-modified')
        except StopIteration:
            pprint(res)
            raise

        print(f"Stop at {r['payload']['bkpt']['original-location']}: {r['message']}")
        if r['payload']['bkpt']['original-location'] == INIT_FRAME:
            xcode, xfirst_instr, xfilename, xname = init_frame(rr)
            print('-+' * 40)
            print(f'Got code={xcode:#x}')
            print(f'Got first_instr={xfirst_instr:#x}')
            print(f'Got filename={xfilename!r}')
            print(f'Got name={xname!r}')

            code.append(xcode)
            first_instr.append(xfirst_instr)
            next_instr.append(xfirst_instr)
            filename.append(xfilename)
            name.append(xname)
            instr_lb.append(0)
            instr_ub.append(-1)
            instr_prev.append(-1)

            cmds = ['enable 2',
                    'enable 3',
                    'watch next_instr']
            cmds += [f'enable {brk_id}' for line, brk_id in dispatch_brk_ids.items()]
            res = rr.write(cmds, timeout_sec=100)
            pprint(res)
        elif ((r['payload']['bkpt']['original-location'] == FAST_NEXT_OPCODE)
                or (int(r['payload']['bkpt']['number']) in dispatch_brk_ids.values())
                or (r['message'] == 'breakpoint-modified'
                 and r['payload']['bkpt']['disp'] == 'keep'
                 and r['payload']['bkpt']['original-location'] == 'next_instr')):
            f_lasti = next_instr[-1] - first_instr[-1]
            print(bcolors.OKGREEN + f'running next_instr (f_lasti = {f_lasti})...' + bcolors.ENDC)
#            pprint(res)
            try:
                next_instr[-1] = get_next_instr(rr)
            except ValueError:
                print('skipping get_next_instr() because it is optimized out')

            print(bcolors.OKGREEN + f'Got next_instr={next_instr[-1]:#x}' + bcolors.ENDC)

            # If the last instruction executed isn't in the current
            # instruction window, reset the window.
            #if f_lasti < instr_lb[-1] or f_lasti >= instr_ub[-1]:
            lineno, instr_lb[-1], instr_ub[-1] = get_lineno(rr, code[-1], f_lasti)

            # If the last instruction falls at the start of a line or if
            # it represents a jump backwards, update the frame's line
            # number and call the trace function.
            #if f_lasti == instr_lb[-1] or f_lasti < instr_prev[-1]:
            print(bcolors.OKGREEN + f'Got {filename[-1]}:{name[-1]}:{lineno}' + bcolors.ENDC)

            instr_prev[-1] = f_lasti
        elif r['payload']['bkpt']['original-location'] == END_FRAME:
            print(bcolors.OKGREEN + 'pop stack')
            code.pop()
            first_instr.pop()
            next_instr.pop()
            filename.pop()
            name.pop()
            instr_lb.pop()
            instr_ub.pop()
            instr_prev.pop()
    rr.exit()
    

if __name__ == '__main__':
    main()

