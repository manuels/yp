import ctypes

def f():
  print('f1')
#  ctypes.string_at(0)
  print('f2')
  x = 1
  return 1

def g():
    print('g')

def main():
  y = 2
  y = y + 1
  print(0)
  y = y + 2
  f()
  y = y + 3
  print(1)
  y = y + 4
  g()
  y = y + 5
  print(y)


if __name__ == '__main__':
  main()
  
print('EOF 00')

import dis
print(dis.dis(f))
print(dis.dis(g))
print(dis.dis(main))

