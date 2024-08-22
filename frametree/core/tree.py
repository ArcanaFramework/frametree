from __future__ import annotations
import logging
import typing as ty
import re
from collections import defaultdict
import attrs
import attrs.filters
from frametree.core.utils import NestedContext
from frametree.core.axes import Axes
from frametree.core.exceptions import (
    FrameTreeNameError,
    FrameTreeConstructionError,
)
from .row import DataRow

if ty.TYPE_CHECKING:  # pragma: no cover
    from .frameset.base import FrameSet


logger = logging.getLogger("frametree")


def auto_ids_default():
    return defaultdict(dict)


@attrs.define
class DataTree(NestedContext):

    frameset: ty.Optional[FrameSet] = None
    root: ty.Optional[DataRow] = None
    _auto_ids: ty.Dict[ty.Tuple[str, ...], ty.Dict[str, int]] = attrs.field(
        factory=auto_ids_default
    )

    def enter(self):
        assert self.root is None
        self._set_root()
        self.frameset.store.populate_tree(self)

    def exit(self):
        self.root = None

    @property
    def dataset_id(self):
        return self.frameset.id

    @property
    def hierarchy(self):
        return self.frameset.hierarchy

    def add_leaf(
        self, tree_path, metadata: ty.Dict[str, ty.Dict[str, str]] = None
    ) -> ty.Tuple[DataRow, ty.List[str]]:
        """Creates a new row at a the path down the tree of the dataset as
        well as all "parent" rows upstream in the data tree

        Parameters
        ----------
        tree_path : list[str]
            The sequence of labels for each layer in the hierarchy of the
            dataset leading to the current row.
        metadata : dict[str, ty.Dict[str, str]]
            metadata passed to ``Store.infer_ids()`` used to infer IDs not directly
            represented in the hierarchy of the data tree.

        Returns
        -------
        row : DataRow or None
            the added row if it is not excluded, None if it was excluded
        exclusions : list[str]
            the list of frequencies that caused the leaf to be excluded (empty if it
            was added) according to the the exclusion criteria provided to the dataset
            (see ``FrameSet.include`` and ``FrameSet.exclude``)

        Raises
        ------
        FrameTreeBadlyFormattedIDError
            raised if one of the IDs doesn't match the pattern in the
            `id_patterns`
        FrameTreeConstructionError
            raised if one of the groups specified in the ID inference reg-ex
            doesn't match a valid row_frequency in the data dimensions
        """

        def matches_criteria(
            label: str, freq_str: str, criteria: ty.Dict[str, ty.Union[list, str]]
        ):
            try:
                freq_criteria = criteria[freq_str]
            except KeyError:
                return None
            if isinstance(freq_criteria, list):
                return label in freq_criteria
            else:
                return bool(re.match(freq_criteria, label))

        if self.root is None:
            self._set_root()
        if metadata is None:
            metadata = {}
        # Get basis frequencies covered at the given depth of the
        if len(tree_path) != len(self.frameset.hierarchy):
            raise FrameTreeConstructionError(
                f"Tree path ({tree_path}) should have the same length as "
                f"the hierarchy ({self.frameset.hierarchy}) of {self}"
            )
        if self.frameset.exclude:
            for freq_str, label in zip(self.frameset.hierarchy, tree_path):
                if matches_criteria(label, freq_str, self.frameset.exclude):
                    return None  # Don't add leaf
        # Set a default ID of None for all parent frequencies that could be
        # inferred from a row at this depth
        # ids = {f: None for f in self.frameset.axes}
        ids = dict(zip(self.frameset.hierarchy, tree_path))
        # Infer IDs and add them to those explicitly in the hierarchy
        inferred_ids = self.frameset.infer_ids(ids, metadata=metadata)
        ids.update(inferred_ids)
        # Calculate the combined freqs after each layer is added
        cummulative_freq = self.frameset.axes(0)
        for i, layer_str in enumerate(self.frameset.hierarchy):
            layer_freq = self.frameset.axes[layer_str]
            # If all the axes introduced by the layer not present in parent layers
            # and none of the IDs of these axes have been inferred from other IDs,
            # then the ID of the axis out of the layer's axes with the least-
            # significant bit can be considered to be equivalent to the
            # ID of the layer and the IDs of the other axes of the layer set to None
            # (the order of # the bits in the Axes class should be arranged to
            # account for this default behaviour).
            #
            # For example, given a hierarchy of ['subject', 'session'] in the `Clinical`
            # data space, no groups are assumed to be present by default (i.e. if not
            # specified by the `id_patterns` attr of the dataset), and the `member`
            # ID is assumed to be equivalent to the `subject` ID, since `member`
            # correspdonds to the least significant bit in the value of the subject in
            # the `Clinical` data space enum.
            #
            # Conversely, the visit can't be assumed to be equal to the `session`
            # ID, since the session ID could be expected to also contain both the `member` and
            # `group` ID in it, and should be explicitly extracted by via `id_patterns`
            #
            #       session ID: MRH010_CONTROL03_MR02
            #
            # with the '02' part representing as the visit can be extracted with the
            #
            #       id_inference = {
            #           'visit': r'session:id:.*MR(0-9+)$'
            #       }
            # Axes already added by predecessor layers
            prev_accounted_for = layer_freq & cummulative_freq
            # Axes added by this layer
            new = prev_accounted_for ^ layer_freq
            assert new, f"{layer_str} doesn't add any new axes on predecessor layers"
            layer_span = [str(f) for f in layer_freq.span()]
            # Axes that have an ID already
            unresolved_axes = [f for f in layer_span if f not in ids]
            if unresolved_axes:
                for axis in unresolved_axes[:-1]:
                    ids[axis] = None
                # If all axes added by the layer are new and none are resolved to IDs
                # we can just use the ID for the layer to be equivalent to the last axis
                if not prev_accounted_for and unresolved_axes == layer_span:
                    assumed_id = ids[layer_str]
                else:
                    node_path = tuple(tree_path[:i]) + tuple(
                        ids[str(f)] for f in new.span() if str(f) in ids
                    )
                    layer_label = tree_path[i]
                    try:
                        assumed_id = self._auto_ids[node_path][layer_label]
                    except KeyError:
                        assumed_id = str(len(self._auto_ids[node_path]) + 1)
                        self._auto_ids[node_path][layer_label] = assumed_id
                ids[unresolved_axes[-1]] = assumed_id
            cummulative_freq |= layer_freq
        assert cummulative_freq == self.frameset.axes.leaf()
        assert set(ids).issuperset(str(f) for f in self.frameset.axes.bases())
        # # Set or override any inferred IDs within the ones that have been
        # # explicitly provided
        # clashing_ids = set(ids) & set(additional_ids)
        # if clashing_ids:
        #     raise FrameTreeUsageError(
        #         f"Additional IDs clash with those inferred: {clashing_ids}"
        #     )
        # ids.update(additional_ids)
        # Create composite IDs for non-basis frequencies if they are not
        # explicitly in the layer dimensions
        for freq in set(self.frameset.axes) - set(self.frameset.axes.bases()):
            freq_str = str(freq)
            if freq_str not in ids:
                id_ = tuple(ids[str(b)] for b in freq.span() if ids[str(b)] is not None)
                if id_:
                    if len(id_) == 1:
                        id_ = id_[0]
                else:
                    id_ = None
                ids[freq_str] = id_
        # Determine whether leaf node is included in the dataset definition according
        # to the include and exclude criteria
        if self.frameset.include:
            for freq in self.frameset.axes:
                freq_str = str(freq)
                if (
                    matches_criteria(ids[freq_str], freq_str, self.frameset.include)
                    is False
                ):
                    return None
        return self._add_row(
            ids={f: ids.get(str(f)) for f in self.frameset.axes},
            row_frequency=self.frameset.axes.leaf(),
        )

    def _add_row(self, ids: ty.Dict[Axes, str], row_frequency):
        """Adds a row to the dataset, creating all parent "aggregate" rows
        (e.g. for each subject, group or visit) where required

        Parameters
        ----------
        ids : dict[Axes, str]
            ids of the row in all frequencies that it intersects
        row: DataRow
            The row to add into the data tree

        Raises
        ------
        FrameTreeConstructionError
            If inserting a multiple IDs of the same class within the tree if
            one of their ids is None
        """
        # logger.debug(
        #     "Found %s row in %s dataset: %s", row_frequency, self.dataset_id, ids
        # )
        row_frequency = self.frameset.parse_frequency(row_frequency)
        row = DataRow(ids=ids, frequency=row_frequency, frameset=self.frameset)
        # Create new data row
        try:
            row_dict = self.root.children[row.frequency]
        except KeyError:
            row_dict = self.root.children[row.frequency] = {}
        if row.id in row_dict:
            raise FrameTreeConstructionError(
                f"ID clash ({row.id}) between rows inserted into the data tree of "
                f"{self.frameset.id} in {self.frameset.store.name} store:\n"
                "  exist: "
                + ", ".join(f"{f}={i}" for f, i in sorted(row_dict[row.id].ids.items()))
                + "\n  added: "
                + ", ".join(f"{f}={i}" for f, i in sorted(row.ids.items()))
            )
        row_dict[row.id] = row
        # Insert root row
        # Insert parent rows if not already present and link them with
        # inserted row
        for parent_freq, parent_id in row.ids.items():
            if not parent_freq:
                continue  # Don't need to insert root row again
            diff_freq = (row.frequency ^ parent_freq) & row.frequency
            if diff_freq:
                try:
                    parent_row = self.frameset.row(frequency=parent_freq, id=parent_id)
                except FrameTreeNameError:
                    parent_ids = {
                        f: i
                        for f, i in row.ids.items()
                        if f.is_parent(parent_freq, if_match=True)
                    }
                    parent_row = self._add_row(parent_ids, parent_freq)
                # Set reference to level row in new row
                diff_id = row.frequency_id(diff_freq)
                try:
                    children_dict = parent_row.children[row_frequency]
                except KeyError:
                    children_dict = parent_row.children[row_frequency] = {}
                if diff_id in children_dict:
                    raise FrameTreeConstructionError(
                        f"ID clash between rows inserted into data tree, {diff_id}, "
                        f"in {diff_freq} children of {parent_row} "
                        f"({children_dict[diff_id]} and {row}). You may "
                        f"need to set the `id_patterns` attr of the dataset "
                        "to disambiguate ID components (e.g. how to extract "
                        "the visit ID from a session label)"
                    )
                children_dict[diff_id] = row
        return row

    def _set_root(self):
        self.root = DataRow(
            ids={self.frameset.root_freq: None},
            frequency=self.frameset.root_freq,
            frameset=self.frameset,
        )
        self._auto_ids = auto_ids_default()
