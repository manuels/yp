import dataclasses
from collections import OrderedDict
from pathlib import Path
import warnings
import logging
import functools
import contextlib
import enum

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)
#log.setLevel(logging.DEBUG)
#log.debug = print

INIT_FRAME_LINE = '../Python/ceval.c:1324'  # in _PyEval_EvalFrameDefault: next_instr = first_instr;
END_FRAME_LINE = '../Python/ceval.c:3844'   # in _PyEval_EvalFrameDefault: tstate->frame = f->f_back;

import yp
gdb = yp.gdb
gdbenv = yp.gdbenv
from yp.gdb_utils import *

STACK = []

class NextInstrOptimizationWarning(RuntimeWarning):
    pass
    
warnings.simplefilter('once', NextInstrOptimizationWarning)


def get_pygdb_selected_frame():
    _gdbframe = gdb.selected_frame()
    if _gdbframe:
        return yp.gdbenv.Frame(_gdbframe)
    return None


"""
@gdb_command("py-foo", gdb.COMMAND_RUNNING, gdb.COMPLETE_NONE)
def invoke(cmd, args, from_tty):
#    print(get_pygdb_selected_frame())
#    print(get_pygdb_selected_frame().get_pyop())
    pyop = get_pygdb_selected_frame().get_pyop()
    filename = pyop.filename()
    lineno = pyop.current_line_num()
#    print(f'{filename}:{lineno}')
"""


@dataclasses.dataclass
class PyStackFrame:
    class NoActiveFrame(Exception):
        pass

    code: int
    first_instr: int
    filename: str
    func: str

    next_instr: int
    instr_lb: int
    instr_ub: int
    instr_prev: int

    def __init__(self, values=None):
        if values is None:
            with frame_up():
                self.code = int(gdb.parse_and_eval('f.f_code'))
                lasti = int(gdb.parse_and_eval('f.f_lasti'))
                self.filename = str(gdb.parse_and_eval('f.f_code.co_filename'))
                self.func = str(gdb.parse_and_eval('f.f_code.co_name'))
        else:
            self.code, lasti, self.filename, self.func = values

        q = f'(((PyCodeObject *)({self.code}))->co_code)'
        q = f'(((PyBytesObject *)({q}))->ob_sval)'
        q = f'((_Py_CODEUNIT *) {q})'
        self.first_instr = int(gdb.parse_and_eval(q))

        if ExecDirection.get_exec_direction() == ExecDirection.FORWARD:
            self.next_instr = self.first_instr
            self.instr_lb = lasti
            self.instr_ub = lasti
            self.instr_prev = lasti
        else:
            self.next_instr = self.first_instr + lasti
            self.instr_lb = 0
            self.instr_ub = -1
            self.instr_prev = -1

    @classmethod
    def from_py_frame_object_ptr(cls, py_frame):
        code = py_frame.co.as_address()
        lasti = py_frame.f_lasti
        filename = py_frame.co_filename
        func = py_frame.co_name
        return cls(values=(code, lasti, filename, func))

    @property
    def lasti(self):
        return self.next_instr - self.first_instr

    def is_at_new_line(self, lasti):
        # If the last instruction falls at the start of a line or if
        # it represents a jump backwards, update the frame's line
        # number and call the trace function.

        print(f'lasti = {lasti}, instr_ub = {self.instr_ub}, instr_lb={self.instr_lb}, instr_prev={self.instr_prev}')
        if ExecDirection.get_exec_direction() == ExecDirection.FORWARD:
            #return lasti == self.instr_lb or lasti < self.instr_prev
            return lasti >= self.instr_lb or lasti < self.instr_prev
        else:
            return lasti == self.instr_lb or lasti >= self.instr_ub

    @property
    def lineno(self):
        # If the last instruction executed isn't in the current
        # instruction window, reset the window.

        if self.lasti < self.instr_lb or self.lasti >= self.instr_ub:
            self.update_lineno()
        return self._lineno

    def update_lineno(self):
        with malloc('sizeof(PyAddrPair)') as bounds:
            int(gdb.parse_and_eval(f'(((PyAddrPair *) {bounds}).ap_lower) = 0'))
            int(gdb.parse_and_eval(f'(((PyAddrPair *) {bounds}).ap_upper) = 0'))

            self._lineno = int(gdb.parse_and_eval(f'_PyCode_CheckLineNumber({self.code}, {self.lasti}, {bounds})'))

            self.instr_lb = int(gdb.parse_and_eval(f'((PyAddrPair *) {bounds}).ap_lower'))
            self.instr_ub = int(gdb.parse_and_eval(f'((PyAddrPair *) {bounds}).ap_upper'))


    def __repr__(self):
        return f'StackFrame<{self.filename}:{self.lineno} {self.func} lasti={self.lasti} nexti={self.next_instr:#x} firsti={self.first_instr:#x}>'

    def update_instr(self):
        next_instr_expr = gdb.parse_and_eval('next_instr')
        if not next_instr_expr.is_optimized_out:
            self.instr_prev = self.lasti
            self.next_instr = int(next_instr_expr)
            fn = gdb.newest_frame().name()
        else:
            _, (symtab_and_line,) = gdb.decode_line()
            fn = symtab_and_line.symtab.filename
            fn_lineno = symtab_and_line.f_lineno
            #warnings.warn(f'next_instr is optimized out in {fn}:{fn_lineno}', NextInstrOptimizationWarning)
            log.warning(f'next_instr is optimized out in {fn}:{fn_lineno}')


def gdb_breakpoint(func_or_line, cls=gdb.Breakpoint):
    def build_class(func):
        klass = type(func.__name__, (cls, ), dict(stop=func))
        return klass

    if callable(func_or_line):
        func = func_or_line
        klass = build_class(func)
        return klass
    else:
        line = func_or_line
        def wrapper2(func):
            klass = build_class(func)
            return functools.partial(klass, line)
        return wrapper2


class InitStackFrameBreakpoint(gdb.Breakpoint):
    def __init__(self, brk_list, *args):
        log.debug(INIT_FRAME_LINE, *args)
        gdb.Breakpoint.__init__(self, INIT_FRAME_LINE, *args)
        self.brk_list = brk_list

    def stop(self):
        log.debug(f'stop InitStackFrameBreakpoint depth={len(STACK)} {STACK[-1] if len(STACK) else ""}')

        # TODO: replace by change_frame(self, self.brk_list)
        if ExecDirection.get_exec_direction() == ExecDirection.FORWARD:
            enter_frame()
        else:
            leave_frame(self, self.brk_list)
        
        return False


def enter_frame():
    STACK.append(PyStackFrame())


def leave_frame(self_brk, brk_list):
    if STACK:
        STACK.pop()

    log.debug(f'leave_frame depth={len(STACK)}')

    if not STACK:
        for brk in brk_list:
            if brk != self_brk:
                brk.delete()
        self_brk.enabled = False  # TODO we cannot delete ourself


class EndStackFrameBreakpoint(gdb.Breakpoint):
    def __init__(self, brk_list, *args):
        gdb.Breakpoint.__init__(self, END_FRAME_LINE, *args)
        self.brk_list = brk_list

    def stop(self):
        log.debug(f'stop EndStackFrameBreakpoint depth={len(STACK)}')
        log.info('get_pygdb_selected_frame', get_pygdb_selected_frame().get_pyop())

        if ExecDirection.get_exec_direction() == ExecDirection.FORWARD:
            leave_frame(self, self.brk_list)
        else:
            # TODO raise NotImplemented('What to do in reverse direction here?')
            enter_frame()
        
        return False


class ConditionalBreakpoint(gdb.Breakpoint):
    def __init__(self, position, condition=None):
        gdb.Breakpoint.__init__ (self, position)
        self.condition = condition

    def should_stop(self):
        if self.condition:
            v = gdb.parse_and_eval(self.condition)
            return v != 0
        else:
            return True


def ceval_case_target_lines():
    contents = (Path(__file__).parent / 'ceval-py392.c').read_text().splitlines()
    lines = [l for i, l in enumerate(contents)]
    lineno_list = [i + 1 for i, l in enumerate(contents) if r'case TARGET(' in l]
    assert len(lineno_list) > 0
    return lineno_list

# these `case` statements are all in _PyEval_EvalFrameDefault:
CASE_TARGET_LIST = [f'../Python/ceval.c:{lineno}' for lineno in ceval_case_target_lines()]


STEP_MODE = None


if False:
    def get_current_pyframe():
        return STACK[-1]
else:
    def get_current_pyframe():
        frame: gdbenv.PyFrameObjectPtr = gdbenv.Frame.get_selected_python_frame().get_pyop()
        return PyStackFrame.from_py_frame_object_ptr(frame)


@gdb_breakpoint
def NextInstrBreakpoint(brk):
    global STEP_MODE
    frame = get_current_pyframe()
    ret = False

    lasti = frame.lasti
    frame.update_instr()

    at_new_line = frame.is_at_new_line(frame.lasti)
    if at_new_line and STEP_MODE == 'step':
        #gdb.execute('py-bt')
        STEP_MODE = None
        ret = True
    if STEP_MODE == 'op':
        STEP_MODE = None
        ret = True

    print(f'stop NextInstrBreakpoint {frame} at_new_line={at_new_line}, mode={STEP_MODE}')
    log.debug(f'stop NextInstrBreakpoint {frame}')
    return ret


@gdb_breakpoint(INIT_FRAME_LINE, cls=ConditionalBreakpoint)
def UserInitStackFrameBreakpoint(brk):
    if not brk.should_stop():
        return False

    log.debug(f'stop UserInitStackFrameBreakpoint depth={len(STACK)} {get_current_pyframe()}')

    gdb.execute('py-bt')

    return True


@gdb_command("py-break", gdb.COMMAND_BREAKPOINTS, gdb.COMPLETE_LOCATION)
def invoke(cmd, args, from_tty):
    try:
        filename, location = args.rstrip().rsplit(':')
    except ValueError:
        gdb.write('Expected py-break <script_file:lineno/function>\n')
        return

    where = f'$_streq({gdb_escape(filename)}, {py_string("co.co_filename")})'
    
    try:
        lineno = int(location)
    except ValueError:
        func = location        
        where += f' && $_streq({gdb_escape(func)}, {py_string("co.co_name")})'
    else:
        gdb.write('py-break only accepts function names (and no line numbers) right now.\n')
        return

    brk = UserInitStackFrameBreakpoint(where)


@gdb_command("py-step-old", gdb.COMMAND_RUNNING, gdb.COMPLETE_NONE)
def invoke(cmd, args, from_tty):
    global STEP_MODE
    STEP_MODE = 'step'

    try:
        frame = PyStackFrame()
    except PyStackFrame.NoActiveFrame:
        gdb.write('No active python frame!\n')  # TODO set breakpoint and wait until we have one
        return

    STACK.append(frame)

    brk_args = OrderedDict(type=gdb.BP_BREAKPOINT,
                           wp_class=gdb.WP_WRITE,
                           internal=True,
                           temporary=True)

    if len(STACK) == 1:
        cleanup_list = []
        init_frame_brk = InitStackFrameBreakpoint(cleanup_list, *brk_args.values())
        next_instr_brk_list = [NextInstrBreakpoint(position, *brk_args.values()) for position in CASE_TARGET_LIST]
        end_frame_brk = EndStackFrameBreakpoint(cleanup_list, *brk_args.values())

        cleanup_list += [init_frame_brk, end_frame_brk] + next_instr_brk_list

    gdb.execute('continue')


@gdb_command("py-reverse-step-old", gdb.COMMAND_RUNNING, gdb.COMPLETE_NONE)
def invoke(cmd, args, from_tty):
    global STEP_MODE
    STEP_MODE = 'step'
    gdb.execute('reverse-continue')


import yp.cmd_stepi
import yp.cmd_step


# TODOs
# [ ] break at line
# [x] stepi
# [x] step
# [ ] finish
# [ ] next
# [ ] better stack handling
# [ ] rstep
# [ ] rnext
# [ ] py-break autocompletion


