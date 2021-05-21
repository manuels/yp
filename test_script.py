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
  y += 2
  print(0)
  y += 2
  f()
  y += 2
  print(1)
  y += 1
  g()
  y += 1
  print(y)


if __name__ == '__main__':
  main()
  
print('EOF 00')

import dis
print(dis.dis(f))
print(dis.dis(g))
print(dis.dis(main))

