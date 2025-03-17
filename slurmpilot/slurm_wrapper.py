import logging

from slurmpilot.slurmpilot import SlurmPilot


class SlurmWrapper(SlurmPilot):
    def __init__(self, **kwargs):
        super(SlurmWrapper, self).__init__(**kwargs)

        logging.warning(
            "Using SlurmWrapper is deprecated and going to be remove in a the next release. "
            'Use SlurmPilot instead, for instance use "from slurmpilot import SlurmPilot" instead of '
            '"from slurmpilot import SlurmWrapper"'
        )
