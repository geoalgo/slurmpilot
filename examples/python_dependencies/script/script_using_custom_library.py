# we use a library from another folder that is being copied over and added to Python path by slurmpilot
from custom_library.speed_of_light import speed_of_light

if __name__ == '__main__':
    print(speed_of_light())