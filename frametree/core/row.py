from __future__ import annotations
import typing as ty
import attrs
import natsort
from frametree.core.exceptions import (
    FrameTreeNameError,
    FrameTreeWrongFrequencyError,
)
from fileformats.core import DataType
from pydra.utils.hash import (
    register_serializer,
    Cache,
    bytes_repr_mapping_contents,
)
from .quality import DataQuality
from .axes import Axes
from .cell import DataCell
from .entry import DataEntry


if ty.TYPE_CHECKING:  # pragma: no cover
    from .frameset.base import FrameSet


@attrs.define(kw_only=True)
class DataRow:
    """A "row" in a dataset "frame" where file-sets and fields can be placed, e.g.
    a session or subject.

    Parameters
    ----------
    ids : Dict[Axes, str]
        The ids for the frequency of the row and all "parent" frequencies
        within the tree
    dataset : FrameSet
        A reference to the root of the data tree
    frequency : str
        The frequency of the row
    tree_path : list[str], optional
        the path to the row within the data tree. None if the row doesn't sit within
        the original tree (e.g. visits within a subject>session hierarchy)
    uri : str, optional
        a URI for the row, can be set and used by the data store implementation if
        appropriate, by default None
    """

    ids: dict[Axes, str] = attrs.field()
    frameset: FrameSet = attrs.field(repr=False)
    frequency: Axes = attrs.field()
    tree_path: list[str] | None = None
    uri: str | None = None
    metadata: dict[str, ty.Any] | None = None

    # Automatically populated fields
    children: dict[Axes, dict[str | tuple[str], str]] = attrs.field(
        factory=dict, repr=False, init=False
    )
    _entries_dict: dict[tuple[str, int | str | None], DataEntry] | None = attrs.field(
        default=None, init=False, repr=False
    )
    _cells: dict[str, DataCell] = attrs.field(factory=dict, init=False, repr=False)

    @frameset.validator  # pyright: ignore[reportAttributeAccessIssue]
    def dataset_validator(
        self, _: attrs.Attribute[FrameSet], dataset: "FrameSet"
    ) -> None:
        from .frameset import FrameSet

        if not isinstance(dataset, FrameSet):
            raise ValueError(f"provided dataset {dataset} is not of type {FrameSet}")

    @frequency.validator  # pyright: ignore[reportAttributeAccessIssue]
    def frequency_validator(self, _: attrs.Attribute[Axes], frequency: Axes) -> None:
        if frequency not in self.frameset.axes:
            raise ValueError(
                f"'{frequency}' frequency is not in the data space of the dataset, "
                f"{self.frameset.axes}"
            )

    def __attrs_post_init__(self) -> None:
        if isinstance(self.frequency, str):
            self.frequency = self.frameset.axes[self.frequency]

    def __getitem__(self, column_name: str) -> DataType:
        """Gets the item for the current row

        Parameters
        ----------
        column_name : str
            Name of a selected column in the dataset

        Returns
        -------
        DataType
            The item matching the provided name specified by the column name
        """
        return self.cell(column_name, allow_empty=False).item

    def __setitem__(self, column_name: str, value: DataType) -> DataRow:
        self.cell(column_name).item = value
        return self

    def cell(self, column_name: str, allow_empty: bool | None = None) -> DataCell:
        try:
            cell = self._cells[column_name]
        except KeyError:
            pass
        else:
            if not cell.is_empty:
                return cell
        try:
            column = self.frameset[column_name]
        except KeyError as e:
            raise FrameTreeNameError(
                column_name,
                f"{column_name} is not the name of a column in "
                f"{self.frameset.id} dataset ('"
                + "', '".join(self.frameset.columns)
                + "')",
            ) from e
        if column.row_frequency != self.frequency:
            raise FrameTreeWrongFrequencyError(
                column_name,
                f"'column_name' ({column_name}) is of {column.row_frequency} "
                f"frequency and therefore not in rows of {self.frequency}"
                " frequency",
            )
        cell = DataCell.intersection(column=column, row=self, allow_empty=allow_empty)
        self._cells[column_name] = cell
        return cell

    def cells(self, allow_empty: bool | None = None) -> ty.Iterable[DataCell]:
        for column_name in self.frameset.columns:
            yield self.cell(column_name, allow_empty=allow_empty)

    @property
    def entries(self) -> ty.Iterable[DataEntry]:
        return self.entries_dict.values()

    def entry(
        self, name: str, order: int | None = None, key: int | str | None = None
    ) -> DataEntry:
        """Access an entry from the row

        Parameters
        ----------
        name : str
            The name of the entry
        order : int | None
            The order of the entry, when there are multiple entries with the same name
        key : int | str | None
            The key used to sort the entries of the row

        Return
        ------
        DataEntry
            The entry matching the provided name, and order or key
        """
        if order is not None and key is not None:
            raise ValueError(
                f"Only one of 'order' or 'key' can be provided to DataRow.entry() ({self})"
            )
        try:
            return self.entries_dict[(name, key)]
        except KeyError:
            keys = natsort.natsorted(k[1] for k in self.entries_dict if k[0] == name)
            if not keys:
                raise KeyError(f"No entries within {self} with name '{name}'")
            if order is not None:
                try:
                    key = keys[order]
                except IndexError:
                    raise KeyError(
                        f"Not enough entries within {self} with name '{name}' to select {order}th entry (keys: {keys})"
                    )
            elif len(keys) == 1:
                key = keys[0]
            else:
                raise KeyError()
            return self.entries_dict[(name, key)]

    @property
    def entries_dict(self) -> dict[tuple[str, int | str | None], DataEntry]:
        if self._entries_dict is None:
            self._entries_dict = {}
            self.frameset.store.populate_row(self)
        return self._entries_dict

    def __repr__(self) -> str:
        return f"{type(self).__name__}(id={self.id}, frequency={self.frequency})"

    @property
    def id(self) -> str:
        return self.ids[self.frequency]

    @property
    def ids_tuple(self) -> tuple[str, ...]:
        return tuple(self.ids[a] for a in self.frameset.axes.bases())

    @property
    def label(self) -> str:
        if self.tree_path is None or not self.tree_path:
            raise AttributeError("tree_path is not set or empty")
        return self.tree_path[-1]

    def frequency_id(self, frequency: ty.Union[str, Axes]) -> str:
        return self.ids[self.frameset.axes[str(frequency)]]

    def __iter__(self) -> ty.Iterator[str]:
        return iter(self.keys())

    def keys(self) -> ty.Generator[str, None, None]:
        return (n for n, _ in self.items())

    def values(self) -> ty.Generator[DataType, None, None]:
        return (i for _, i in self.items())

    def items(self) -> ty.Iterable[tuple[str, DataType]]:
        return (
            (c.name, self[c.name])
            for c in self.frameset.columns.values()
            if c.row_frequency == self.frequency
        )

    def column_items(self, column_name: str) -> list[DataType]:
        """Gets the item for the current row if item's frequency matches
        otherwise gets all the items that are related to the current row (
        i.e. are in child rows)

        Parameters
        ----------
        column_name : str
            Name of a selected column in the dataset

        Returns
        -------
        Sequence[DataType]
            The item matching the provided name specified by the column name
            if the column is of matching or ancestor frequency, or list of
            items if a descendent or unrelated frequency.
        """
        try:
            return [self[column_name]]
        except FrameTreeWrongFrequencyError:
            # If frequency is not a ancestor row then return the
            # items in the children of the row (if they are child
            # rows) or the whole dataset
            spec = self.frameset.columns[column_name]
            try:
                # Assume children values are DataEntry, return their .item
                return [
                    entry.item for entry in self.children[spec.row_frequency].values()
                ]
            except KeyError:
                # If frameset.column does not exist, raise a clear error
                raise AttributeError(
                    f"frameset has no attribute 'column' for frequency {spec.row_frequency}"
                )

    def create_entry(
        self, path: str, datatype: type[DataType], order_key: int | str | None = None
    ) -> DataEntry:
        """Creates a new data entry for the row, i.e. modifies the data in the store

        Parameters
        ----------
        path : str
            the path to the entry to be created within the node, e.g. 'resources/ml-summary.json'
        datatype : type (subclass of fileformats.core.DataType)
            the type of the data entry
        order_key : str or int, optional
            the order of the entry within the row, can be used to disambiguate
            entries with the same path

        Returns
        -------
        DataEntry
            The newly created data entry
        """
        return self.frameset.store.create_entry(
            path=path, datatype=datatype, row=self, order_key=order_key
        )

    def add_entry(
        self,
        path: str,
        datatype: type[DataType],
        uri: str,
        item_metadata: dict[str, ty.Any] | None = None,
        order_key: int | str | None = None,
        quality: DataQuality = DataQuality.usable,
        checksums: dict[str, str | dict[str, ty.Any]] | None = None,
    ) -> DataEntry:
        """Adds an existing data entry to a row that has been found while scanning the
        row in the repository.

        Parameters
        ----------
        path : str
            the path to the entry to be created within the node, e.g. 'resources/ml-summary.json'
        datatype : type (subclass of DataType)
            the type of the data entry
        uri : str
            a URI uniquely identifying the data entry, which can be used by the store
            for convenient/efficient access to the entry. Note that newly added entries
            (i.e. created by data-sink columns) will not have their URI set, so data
            store logic should fallback to using the row+id to identify the entry in
            the dataset.
        item_metadata : dict[str, Any]
            metadata associated with the data item itself (e.g. pulled from a file header).
            Can be supplied either when the entry is initialised (i.e. from previously
            extracted fields stored within the data store), or read from the item itself.
        order : int, optional
            the order in which the entry appears in the node (where applicable)
        provenance : dict, optional
            the provenance associated with the derivation of the entry by FrameTree
            (only applicable to derivatives not source data)
        checksums : dict[str, str | dict[str, Any]], optional
            checksums for all of the files in the data entry
        """
        if self._entries_dict is None:
            self._entries_dict = {}
        # Cast checksums to expected type if needed
        entry = DataEntry(
            path=path,
            datatype=datatype,
            row=self,
            uri=uri,
            item_metadata=item_metadata,
            order_key=order_key,
            quality=quality,
            checksums=checksums if checksums is not None else {},
        )
        if (path, order_key) in self._entries_dict:
            raise KeyError(
                f"Attempting to add multiple entries with the same path, '{path}', to "
                f"{self}, {self._entries_dict[(path, order_key)]} and {entry}"
            )
        self._entries_dict[(path, order_key)] = entry
        return entry


@register_serializer(DataRow)  # type: ignore[misc]
def bytes_repr_data_row(row: DataRow, cache: Cache) -> ty.Iterator[bytes]:
    yield "frametree.core.row.DataRow:(".encode()
    yield b"frameset.id="
    yield row.frameset.id.encode()
    yield b", ids="
    yield from bytes_repr_mapping_contents(row.ids, cache)
    yield b")"
