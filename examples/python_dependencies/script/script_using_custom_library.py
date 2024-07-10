# we use a library from another folder that is being copied over and added to Python path by slurmpilot
from custom_library.speed_of_light import speed_of_light

if __name__ == '__main__':
    print(
        f"The speed of light is {speed_of_light()} m/s. \n"
        f"To get this number, slurmpilot copied the custom libary and "
        f"added its path the PYTHONPATH. Life is beautiful."
    )
