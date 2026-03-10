import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app import GameFinderApp

def main():
    app = GameFinderApp()
    app.mainloop()

if __name__ == "__main__":
    main()
