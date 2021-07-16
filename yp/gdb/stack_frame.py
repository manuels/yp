import warnings
import dataclasses

import logging
log = logging.getLogger(__name__)

import yp
from yp.gdb.utils import frame_up, ExecDirection, malloc
from yp.yp_gdb import STACK

import gdb
gdbenv = yp.gdbenv


class NextInstrOptimizationWarning(RuntimeWarning):
    pass

warnings.simplefilter('once', NextInstrOptimizationWarning)

def get_current_pyframe():
    frame: gdbenv.PyFrameObjectPtr = gdbenv.Frame.get_selected_python_frame().get_pyop()
    return PyStackFrame.from_py_frame_object_ptr(frame)


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


def get_pygdb_selected_frame():
    _gdbframe = gdb.selected_frame()
    if _gdbframe:
        return yp.gdbenv.Frame(_gdbframe)
    return None


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