import os
import sys

if __name__ == "__main__":
    print(
        f"Hello there, here are the command line arguments {sys.argv}\nAnd the current environment variables: {os.environ}"
    )
