#!/usr/bin/env python3

from pygdbmi.gdbcontroller import GdbController
from pprint import pprint


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


CODE = '../Python/ceval.c:1299'
FIRST_INSTR = '../Python/ceval.c:1325'
F_EXECUTING = '../Python/ceval.c:1332'
FAST_NEXT_OPCODE = '../Python/ceval.c:1407'


def get_first_instr(rr):
    res = rr.write(f'-data-evaluate-expression next_instr', timeout_sec=1)
#    res = rr.write(f'print (((PyBytesObject *)(co->co_code))->ob_sval)', timeout_sec=1)
    assert res[0]['message'] == 'done', f'first_instr failed: {res!r}'
    first_instr = res[0]['payload']['value']
    first_instr = int(first_instr, base=16)
    return first_instr


def handle_throwflag(rr):
    res = rr.write(f'-data-evaluate-expression co', timeout_sec=1)
    assert res[0]['message'] == 'done', f'f.f_code failed: {res!r}'
    f_code = res[0]['payload']['value']
    f_code = int(f_code, base=16)

    res = rr.write(f'print (char*) (((PyASCIIObject*) f.f_code.co_filename) + 1)', timeout_sec=1)
    co_filename = res[1]['payload']

    res = rr.write(f'print (char*) (((PyASCIIObject*) f.f_code.co_name) + 1)', timeout_sec=1)
    co_name = res[1]['payload']

    return f_code, co_filename, co_name


def handle_fast_next_opcode(rr, first_instr, f_code):
#    res = rr.write(f'-var-create next_instr * next_instr', timeout_sec=1)
    res = rr.write(f'-data-evaluate-expression next_instr', timeout_sec=1)
    assert res[0]['message'] == 'done'
    next_instr = res[0]['payload']['value']
    next_instr = int(next_instr, base=16)

    res = rr.write(f'-data-evaluate-expression malloc(sizeof(PyAddrPair))', timeout_sec=1)
    assert res[0]['message'] == 'done', res
    bounds = res[0]['payload']['value']

    res = rr.write(f'call _PyCode_CheckLineNumber({f_code}, {next_instr} - {first_instr}, {bounds})', timeout_sec=1)
#    assert res[0]['message'] == 'done', res
#    pprint(res)

    print(res[1]['payload'])
    _, lineno = res[1]['payload'].split('=')
    lineno = lineno.strip(' ')
    lineno = lineno.rstrip('\\n')
    lineno = int(lineno)
    
#    res = rr.write(f'-data-evaluate-expression {bounds}.ap_lower', timeout_sec=1)
#    assert res[0]['message'] == 'done', res
#    pprint(res)

#    res = rr.write(f'-data-evaluate-expression {bounds}.ap_upper', timeout_sec=1)
#    assert res[0]['message'] == 'done', res
#    pprint(res)

    return lineno


def main():
    command = ['rr', 'replay', '-o', '--interpreter=mi3', '-o', '--quiet']
    rr = RRController(command=command)

    res = None
    while res is None or  all(r['message'] != 'stopped' for r in res):
        res = rr.get_gdb_response(timeout_sec=1, raise_error_on_timeout=False)
        pprint(res)

    c_encode = lambda x: x
    filename = c_encode('test_script.py')
    
    where = f'(strcmp("{filename}", ((PyASCIIObject*) f.f_code.co_filename) + 1) == 0)'

    cmds = [
#        f'-break-insert {TROWFLAG}',
        f'-break-insert {CODE} -c {where}',
        f'-break-insert {FIRST_INSTR} -c {where}',
        f'-break-insert {FAST_NEXT_OPCODE}',
    ]

    pprint(cmds)
    res = rr.write(cmds, timeout_sec=10)
    pprint(res)
    print()

    print('-+' * 100)

    for _ in range(10000):
        res = rr.write(f'-exec-continue', timeout_sec=100)
        while all(r['message'] != 'stopped' for r in res):
            res += rr.get_gdb_response(timeout_sec=1, raise_error_on_timeout=False)
            pprint(res)

        r = next(r for r in res if r['message'] == 'breakpoint-modified')
        if r['payload']['bkpt']['original-location'] == CODE:
            f_code, co_filename, co_name = handle_throwflag(rr)
        elif r['payload']['bkpt']['original-location'] == FIRST_INSTR:
            first_instr = get_first_instr(rr)
        elif r['payload']['bkpt']['original-location'] == FAST_NEXT_OPCODE:
            lineno = handle_fast_next_opcode(rr, first_instr, f_code)
            print(f'co_filename = {co_filename}')
            print(f'co_name     = {co_name}')
            print(f'lineno      = {lineno}')
        else:
            assert False
    
    """
    [ ] break at python function/line
    [ ] step
    [ ] instruction


set $bounds = malloc(sizeof(struct PyAddrPair))
call _PyCode_CheckLineNumber(frame->f_code, frame->f_lasti, $bounds);
line = ^
call free($bounds)


    PyAddrPair bounds;
    line = _PyCode_CheckLineNumber(frame->f_code, frame->f_lasti, &bounds);
    *instr_lb = bounds.ap_lower;
    *instr_ub = bounds.ap_upper;
    """

    # optimized out: instr_lb, instr_ub

    rr.exit()
    

if __name__ == '__main__':
    main()

