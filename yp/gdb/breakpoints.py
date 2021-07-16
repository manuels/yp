import functools
import gdb

from yp.gdb.stack_frame import enter_frame, leave_frame, get_pygdb_selected_frame, get_current_pyframe
from yp.gdb.utils import ExecDirection
from yp.yp_gdb import STACK

import logging
log = logging.getLogger(__name__)


INIT_FRAME_LINE = '../Python/ceval.c:1324'  # in _PyEval_EvalFrameDefault: next_instr = first_instr;
END_FRAME_LINE = '../Python/ceval.c:3844'   # in _PyEval_EvalFrameDefault: tstate->frame = f->f_back;


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