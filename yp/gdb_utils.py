import contextlib
import enum

import yp
gdb = yp.gdb

def py_string(obj):
    return f'((char *) (((PyASCIIObject *) {obj}) + 1))'


def gdb_escape(s):
    return f'"{s}"'


def gdb_command(name, cmd_class, completer_class=gdb.COMPLETE_NONE):
    def func(func):
        cls = type(func.__name__, (gdb.Command, ), dict(invoke=func))
        instance = cls(name, cmd_class, completer_class=completer_class)
        return instance
    return func


class ExecDirection(enum.Enum):
    FORWARD = enum.auto()
    REVERSE = enum.auto()

    @classmethod
    def get_exec_direction(cls):
        direction = gdb.execute('show exec-direction', from_tty=False, to_string=True).strip()
        if direction == 'Forward.':
            return cls.FORWARD
        elif direction == 'Reverse.':
            return cls.REVERSE
        else:
            raise Exception(f'Unknown exec-direction {repr(direction)}')

    def is_forward(self):
        return self == self.FORWARD

    def is_reverse(self):
        return self == self.REVERSE

    @classmethod
    @contextlib.contextmanager
    def forward(cls):
        direction = cls.get_exec_direction()
        if direction != cls.FORWARD:
            gdb.execute('set exec-direction forward', from_tty=False, to_string=True)

        yield

        if direction == cls.REVERSE:
            gdb.execute(f'set exec-direction reverse', from_tty=False, to_string=True)


@contextlib.contextmanager
def malloc(something):
    with ExecDirection.forward():
        ptr = int(gdb.parse_and_eval(f'malloc({something})'))
        yield ptr
        gdb.execute(f'call free({ptr})', from_tty=False, to_string=True)


@contextlib.contextmanager
def frame_up():
    gdb.execute('up')
    try:
        yield
    finally:
        gdb.execute('down')

