import os
import sys

def main():
    k = os.environ.get("ANTHROPIC_API_KEY")
    if not k:
        print("ANTHROPIC_API_KEY: NOT SET")
        return 1
    print("Length:", len(k))
    print("Last8:", k[-8:])
    return 0

if __name__ == '__main__':
    sys.exit(main())
