from frametree.core.axes import Axes as BaseAxes


class Samples(BaseAxes):
    """
    The most basic data space within only one dimension
    """

    # Root row of the dataset
    constant = 0b0  # constant across the dataset

    # Axes of the data space
    sample = 0b1


# Set default axes for namespace
Axes = Samples
