from __future__ import annotations
import typing as ty
import os
import attrs
from fileformats.core import DataType
from frametree.core.exceptions import FrameTreeDataMatchError, FrameTreeUsageError
from .quality import DataQuality

if ty.TYPE_CHECKING:  # pragma: no cover
    from .row import DataRow


def loaded_converter(
    loaded: ty.Mapping[str, ty.Any] | ty.Sequence[tuple[str, ty.Any]] | None,
) -> dict[str, ty.Any]:
    if loaded is None:
        return {}
    return dict(loaded)


@attrs.define
class ItemMetadata:
    """Metadata that is either manually set at initialisation of the DataEntry (if
    easily extracted from the data store), or lazily loaded from the entry's item if the
    entry datatype"""

    loaded: dict[str, ty.Any] = attrs.field(default=None, converter=loaded_converter)
    _entry: DataEntry = attrs.field(default=None, init=False, repr=False)
    _has_been_loaded: bool = attrs.field(default=False, init=False, repr=False)

    def __iter__(self) -> ty.Iterator[str]:
        raise NotImplementedError

    def __getitem__(self, key: str) -> ty.Any:
        try:
            return self.loaded[key]
        except KeyError:
            if not self._has_been_loaded:
                self.load()
        return self.loaded[key]

    def load(self, overwrite: bool = False) -> None:
        assert self._entry is not None
        # Try to get metadata from the item if it has a metadata attribute
        try:
            item_metadata = getattr(self._entry.item, "metadata", {})
        except AttributeError:
            item_metadata = {}

        if not overwrite:
            mismatching = [
                k
                for k in set(self.loaded) & set(item_metadata)
                if self.loaded[k] != item_metadata[k]
            ]
            if mismatching:
                raise RuntimeError(
                    "Mismatch in values between loaded and loaded metadata values, "
                    "use 'load(overwrite=True)' to overwrite:\n"
                    + "\n".join(
                        f"{k}: loaded={self.loaded[k]}, loaded={item_metadata[k]}"
                        for k in mismatching
                    )
                )
        self.loaded.update(item_metadata)
        self._has_been_loaded = True


@attrs.define()
class DataEntry:
    """An entry in a node of the dataset tree, such as a scan in an imaging
    session in a "session node" or group-level derivative in a "group node"

    Parameters
    ----------
    id : str
        the ID of the entry within the node
    datatype : type (subclass of DataType)
        the type of the data entry
    uri : str, optional
        a URI uniquely identifying the data entry
    item_metadata : dict[str, Any]
        metadata associated with the data item itself (e.g. pulled from a file header).
        Can be supplied either when the entry is initialised (i.e. from previously extracted
        fields stored within the data store), or read from the item itself.
    order_key : int | str, optional
        the key used to order entries within the row appears in the node (where applicable)
    provenance : dict, optional
        the provenance associated with the derivation of the entry by FrameTree
        (only applicable to derivatives not source data)
    checksums : dict[str, str], optional
        checksums for all of the files in the data entry
    """

    path: str = attrs.field()
    datatype: type[DataType]
    row: DataRow
    uri: str
    item_metadata: ItemMetadata = attrs.field(
        default=None, converter=ItemMetadata, repr=False, kw_only=True
    )
    order_key: int | str | None = None
    quality: DataQuality = DataQuality.usable
    checksums: dict[str, str | dict[str, ty.Any]] = attrs.field(
        default=None, repr=False, eq=False
    )
    provenance: dict[str, ty.Any] | None = attrs.field(default=None, repr=False)

    def __attrs_post_init__(self) -> None:
        self.item_metadata._entry = self
        # Validate path
        path, dataset_name = self.split_dataset_name_from_path(self.path)
        if dataset_name and not dataset_name.isidentifier():
            raise FrameTreeUsageError(
                f"Path '{self.path}' has an invalid dataset_name '{dataset_name}')"
            )

    @property
    def item(self) -> DataType:
        return self.get_item()

    @item.setter
    def item(
        self, item: DataType | os.PathLike[str] | int | bool | float | str
    ) -> None:
        if isinstance(item, DataType):
            if not isinstance(item, self.datatype):
                raise FrameTreeDataMatchError(
                    f"Cannot put {item} into {self.datatype} entry of {self.row}"
                )
        else:
            item = self.datatype(item)  # type: ignore
        self.row.frameset.store.put(item, self)

    def get_item(self, datatype: type[DataType] | None = None) -> DataType:
        if datatype is None:
            datatype = self.datatype
        return self.row.frameset.store.get(self, datatype)

    @property
    def recorded_checksums(self) -> dict[str, ty.Any] | None:
        if self.provenance is None:
            return None
        else:
            return self.provenance.get("outputs", {}).get(self.path)  # type: ignore

    @property
    def is_derivative(self) -> bool:
        return self.path_is_derivative(self.path)

    @property
    def base_path(self) -> str:
        return self.split_dataset_name_from_path(self.path)[0]

    @property
    def dataset_name(self) -> str | None:
        return self.split_dataset_name_from_path(self.path)[1]

    @classmethod
    def split_dataset_name_from_path(cls, path: str) -> tuple[str, str | None]:
        parts = path.split("@")
        if len(parts) == 1:
            dataset_name = None
        else:
            path, dataset_name = parts
        if len(parts) > 2:
            raise FrameTreeUsageError(
                f"Entry paths can't have more than one '@' symbol, given {path})"
            )
        return path, dataset_name

    @classmethod
    def path_is_derivative(cls, path: str) -> bool:
        return cls.split_dataset_name_from_path(path)[1] is not None
