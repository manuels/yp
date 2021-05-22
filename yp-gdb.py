from pathlib import Path
import warnings
import logging
import functools
import contextlib

log = logging.getLogger(__name__)
#log.setLevel(logging.INFO)
log.setLevel(logging.DEBUG)
log.debug = print

INIT_FRAME_LINE = '../Python/ceval.c:1324'
END_FRAME_LINE = '../Python/ceval.c:3844'

# rr replay --gdb-x yp-gdb.py


def py_string(obj):
    return f'((char *) (((PyASCIIObject *) {obj}) + 1))'


def gdb_escape(s):
    return f'"{s}"'


def gdb_command(name, cmd_class, completer_class=gdb.COMPLETE_NONE):
    def func(func):
        cls = type(func.__name__, (gdb.Command, ), dict(invoke=func))
        instance = cls(name, cmd_class, )
        return instance
    return func


def get_exec_direction():
    direction = gdb.execute('show exec-direction', from_tty=False, to_string=True).strip()
    if direction == 'Forward.':
        return 'forward'
    elif direction == 'Reverse.':
        return 'reverse'
    else:
        raise Exception(f'Unknown exec-direction {repr(direction)}')

    
@contextlib.contextmanager
def exec_direction_forward():
    direction = get_exec_direction()
    if direction != 'forward':
        gdb.execute('set exec-direction forward', from_tty=False, to_string=True)

    yield        

    if direction == 'reverse':
        gdb.execute(f'set exec-direction reverse', from_tty=False, to_string=True)


@contextlib.contextmanager
def malloc(something):
    with exec_direction_forward():
        ptr = int(gdb.parse_and_eval(f'malloc({something})'))
        yield ptr
        gdb.execute(f'call free({ptr})', from_tty=False, to_string=True)


STACK = []

class NextInstrOptimizationWarning(RuntimeWarning):
    pass
    
warnings.simplefilter('once', NextInstrOptimizationWarning)


def get_pygdb_selected_frame():
    _gdbframe = gdb.selected_frame()
    if _gdbframe:
        return Frame(_gdbframe)
    return None


@gdb_command("py-foo", gdb.COMMAND_RUNNING, gdb.COMPLETE_NONE)
def invoke(cmd, args, from_tty):
    print(get_pygdb_selected_frame())
    print(get_pygdb_selected_frame().get_pyop())
    pyop = get_pygdb_selected_frame().get_pyop()
    filename = pyop.filename()
    lineno = pyop.current_line_num()
    print(f'{filename}#{lineno}')


class StackFrame:
    def __init__(self):
        gdb.execute('up')  # f might be optimized out, but it is still there in the parent frame

        self.code = int(gdb.parse_and_eval('f.f_code'))
        lasti = int(gdb.parse_and_eval('f.f_lasti'))
        
        q = f'(((PyCodeObject *)({self.code}))->co_code)'
        q = f'(((PyBytesObject *)({q}))->ob_sval)'
        q = f'((_Py_CODEUNIT *) {q})'
        self.first_instr = int(gdb.parse_and_eval(q))
        self.filename = str(gdb.parse_and_eval('f.f_code.co_filename'))
        self.func = str(gdb.parse_and_eval('f.f_code.co_name'))

        gdb.execute('down')

        if get_exec_direction() == 'forward':
            self.next_instr = self.first_instr
            self.instr_lb = lasti
            self.instr_ub = lasti
            self.instr_prev = lasti
        else:
            self.next_instr = self.first_instr + lasti
            self.instr_lb = 0
            self.instr_ub = -1
            self.instr_prev = -1

    @property
    def lasti(self):
        return self.next_instr - self.first_instr

    def is_at_new_line(self, lasti):
        # If the last instruction falls at the start of a line or if
        # it represents a jump backwards, update the frame's line
        # number and call the trace function.

        # TODO: adjust for reverse debugging
        return lasti == self.instr_lb or lasti < self.instr_prev

    @property
    def lineno(self):
        # If the last instruction executed isn't in the current
        # instruction window, reset the window.

        # TODO: adjust for reverse debugging
#        if self.lasti < self.instr_lb or self.lasti >= self.instr_ub:
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
        return f'StackFrame<{self.filename}#{self.lineno} {self.func} lasti={self.lasti} nexti={self.next_instr:#x} firsti={self.first_instr:#x}>'

    def update_instr(self):
        next_instr_expr = gdb.parse_and_eval('next_instr')
        if not next_instr_expr.is_optimized_out:
            self.instr_prev = self.lasti
            self.next_instr = int(next_instr_expr)
            fn = gdb.newest_frame().name()
        else:
            _, (symtab_and_line,) = gdb.decode_line()
            fn = symtab_and_line.symtab.filename
            fn_lineno = symtab_and_line.line
            warnings.warn(f'next_instr is optimized out in {fn}#{fn_lineno}', NextInstrOptimizationWarning)


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
        print(INIT_FRAME_LINE, *args)
        gdb.Breakpoint.__init__(self, INIT_FRAME_LINE, *args)
        self.brk_list = brk_list

    def stop(self):
        log.debug(f'stop InitStackFrameBreakpoint depth={len(STACK)} {STACK[-1] if len(STACK) else ""}')

        # TODO: replace by change_frame(self, self.brk_list)
        if get_exec_direction() == 'forward':
            enter_frame()
        else:
            leave_frame(self, self.brk_list)
        
        return False


def enter_frame():
    STACK.append(StackFrame())


def leave_frame(self_brk, brk_list):
    if STACK:
        STACK.pop()

    print(f'leave_frame depth={len(STACK)}')

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

        if get_exec_direction() == 'forward':
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
    contents = Path('/tmp/ceval.c').read_text().splitlines()
    lines = [l for i, l in enumerate(contents)]
    lineno_list = [i + 1 for i, l in enumerate(contents) if r'case TARGET(' in l]
    assert len(lineno_list) > 0
    return lineno_list


CASE_TARGET_LIST = [f'../Python/ceval.c:{lineno}' for lineno in ceval_case_target_lines()]


STEP_MODE = None

@gdb_breakpoint
def NextInstrBreakpoint(brk):
    global STEP_MODE
    frame = STACK[-1]
    ret = False

    lasti = frame.lasti
    frame.update_instr()

    if frame.is_at_new_line(lasti) and STEP_MODE == 'line':
        gdb.execute('py-bt')
        STEP_MODE = None
        ret = True
    if STEP_MODE == 'op':
        STEP_MODE = None
        ret = True

    log.debug(f'stop NextInstrBreakpoint {frame}')
    return ret


@gdb_breakpoint(INIT_FRAME_LINE, cls=ConditionalBreakpoint)
def UserInitStackFrameBreakpoint(brk):
    if not brk.should_stop():
        return False

    STACK.append(StackFrame())
    log.debug(f'stop UserInitStackFrameBreakpoint depth={len(STACK)} {STACK[-1]}')

    brk_args = [gdb.BP_BREAKPOINT, 0, True]

    if len(STACK) == 1:
        cleanup_list = []
        init_frame_brk = InitStackFrameBreakpoint(cleanup_list, *brk_args)
        next_instr_brk_list = [NextInstrBreakpoint(position, *brk_args) for position in CASE_TARGET_LIST]
        end_frame_brk = EndStackFrameBreakpoint(cleanup_list, *brk_args)

        cleanup_list += [init_frame_brk, end_frame_brk] + next_instr_brk_list

    gdb.execute('py-bt')

    return True


@gdb_command("py-break", gdb.COMMAND_BREAKPOINTS, gdb.COMPLETE_NONE)
def invoke(cmd, args, from_tty):
    filename = '/home/manuel/Projects/yp/test_script.py'
    func = 'main'
    
    where = f'$_streq({gdb_escape(filename)}, {py_string("co.co_filename")})'
    where += f' && $_streq({gdb_escape(func)}, {py_string("co.co_name")})'

    brk = UserInitStackFrameBreakpoint(where)


@gdb_command("py-next", gdb.COMMAND_RUNNING, gdb.COMPLETE_NONE)
def invoke(cmd, args, from_tty):
    global STEP_MODE
    STEP_MODE = 'line'
    gdb.execute('continue')


@gdb_command("py-reverse-next", gdb.COMMAND_RUNNING, gdb.COMPLETE_NONE)
def invoke(cmd, args, from_tty):
    global STEP_MODE
    STEP_MODE = 'line'
    gdb.execute('reverse-continue')


gdb.execute('py-break')

