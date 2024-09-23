import os
import sys

if __name__ == "__main__":
    print(
        f"Hello there, here are the current environment variables: {os.environ} and the command line arguments are"
        f"{sys.argv}."
    )
