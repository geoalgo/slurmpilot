# we use a library from another folder that is being copied over and added to Python path by slurmpilot
import argparse
from custom_library.speed_of_light import speed_of_light

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--learning-rate', type=float)
    args = parser.parse_args()
    print(
        f"The speed of light is {speed_of_light()} m/s and the learning-rate passed was {args.learning_rate}. \n"
        f"To get the speed of light number coming from the custom library, "
        f"Slurmpilot copied the custom library and added its path the PYTHONPATH. Life is beautiful ☀️."
    )
