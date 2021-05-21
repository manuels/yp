from pathlib import Path
import warnings
import logging
import functools

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

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


STACK = []

class NextInstrOptimizationWarning(RuntimeWarning):
    pass
    
warnings.simplefilter('once', NextInstrOptimizationWarning)


class StackFrame:
    def __init__(self):
        code = gdb.parse_and_eval('co')
        first_instr = int(gdb.parse_and_eval('first_instr'))
        filename = gdb.parse_and_eval('co.co_filename')
        func = gdb.parse_and_eval('co.co_name')

        self.code = code
        self.filename = filename
        self.func = func
        self.first_instr = first_instr
        self.next_instr = first_instr
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
        return lasti == self.instr_lb or lasti < self.instr_prev

    @property
    def lineno(self):
        # If the last instruction executed isn't in the current
        # instruction window, reset the window.
        if self.lasti < self.instr_lb or self.lasti >= self.instr_ub:
            self.update_lineno()
        return self._lineno

    def update_lineno(self):
        direction = gdb.execute('show exec-direction', from_tty=False, to_string=True).strip()
        if direction != 'Forward.':
            direction = gdb.execute('set exec-direction forward', from_tty=False, to_string=True)
        
        bounds = int(gdb.parse_and_eval('malloc(sizeof(PyAddrPair))'))
        int(gdb.parse_and_eval(f'(((PyAddrPair *) {bounds}).ap_lower) = 0'))
        int(gdb.parse_and_eval(f'(((PyAddrPair *) {bounds}).ap_upper) = 0'))

        self._lineno = int(gdb.parse_and_eval(f'_PyCode_CheckLineNumber({self.code}, {self.lasti}, {bounds})'))

        self.instr_lb = int(gdb.parse_and_eval(f'((PyAddrPair *) {bounds}).ap_lower'))
        self.instr_ub = int(gdb.parse_and_eval(f'((PyAddrPair *) {bounds}).ap_upper'))

        gdb.execute(f'call free({bounds})', from_tty=False, to_string=True)

        if direction == 'Reverse.':
            gdb.execute(f'set exec-direction reverse', from_tty=False, to_string=True)

    def __repr__(self):
        return f'StackFrame<{self.filename}#{self.lineno} {self.func} lasti={self.lasti}>'

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


class InitStackFrameBreakpoint(gdb.Breakpoint):
    def stop(self):
        log.debug(f'stop InitStackFrameBreakpoint depth={len(STACK)} {STACK[-1] if len(STACK) else ""}')
        STACK.append(StackFrame())
        return False


class EndStackFrameBreakpoint(gdb.Breakpoint):
    def __init__(self, brk_list, *args):
        gdb.Breakpoint.__init__ (self, *args)
        self.brk_list = brk_list

    def stop(self):
        log.debug(f'stop EndStackFrameBreakpoint depth={len(STACK)}')
        if STACK:
            STACK.pop()

        if not STACK:
            for brk in self.brk_list:
                brk.delete()
            self.enabled = False  # TODO we cannot delete ourself
        
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


class NextInstrBreakpoint(gdb.Breakpoint):
    def stop(self):
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



class UserInitStackFrameBreakpoint(ConditionalBreakpoint):
    def stop(self):
        if not self.should_stop():
            return False
    
        STACK.append(StackFrame())
        log.debug(f'stop UserInitStackFrameBreakpoint depth={len(STACK)} {STACK[-1]}')

        brk_args = [gdb.BP_BREAKPOINT, 0, True]

        init_frame_brk = InitStackFrameBreakpoint(INIT_FRAME_LINE, *brk_args)

        next_instr_brk_list = [NextInstrBreakpoint(position, *brk_args) for position in CASE_TARGET_LIST]

        end_frame_brk = EndStackFrameBreakpoint([init_frame_brk] + next_instr_brk_list, END_FRAME_LINE, *brk_args)

        gdb.execute('py-bt')

        return True


@gdb_command("py-break", gdb.COMMAND_BREAKPOINTS, gdb.COMPLETE_NONE)
def invoke(cmd, args, from_tty):
    filename = '/home/manuel/Projects/yp/test_script.py'
    func = 'main'
    
    where = f'$_streq({gdb_escape(filename)}, {py_string("co.co_filename")})'
    where += f' && $_streq({gdb_escape(func)}, {py_string("co.co_name")})'

    brk = UserInitStackFrameBreakpoint(INIT_FRAME_LINE, where)


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

