from frametree.core.axes import Axes


class Clinical(Axes):
    """
    An enum used to specify the hierarchy of data trees and the "frequencies" of items
    within dataset typical of medimage research, i.e. subjects split into groups scanned
    at different visits (in longitudinal studies).
    """

    # Root row of the dataset
    constant = 0b000  # constant across the dataset

    # Axes of the data space
    member = 0b001  # subjects relative to their group membership, i.e.
    # matched pairs of test and control subjects should share
    # the same member IDs.
    group = 0b010  # subject groups (e.g. test & control)
    visit = 0b100  # visits in longitudinal studies

    # Combinations
    session = 0b111  # a single session (i.e. a single visit of a subject)
    subject = 0b011  # uniquely identified subject within in the dataset.
    # As opposed to 'member', which specifies a subject in
    # relation to its group (i.e. one subject for each member
    # in each group). For datasets with only one study group,
    # then subject and member are equivalent
    groupedvisit = 0b110  # data from separate groups at separate visits
    matchedvisit = 0b101  # matched members (e.g. test & control) across
    # all groups and visits


class Samples(Axes):
    """
    The most basic data space within only one dimension
    """

    # Root row of the dataset
    constant = 0b0  # constant across the dataset

    # Axes of the data space
    sample = 0b1
