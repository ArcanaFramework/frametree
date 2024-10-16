from __future__ import annotations
from pathlib import Path
import re
from abc import abstractmethod
import typing as ty
import errno
import logging
import json
import attrs
import yaml
from fasteners import InterProcessLock
from fileformats.core import DataType, FileSet, Field
from frametree.core.exceptions import (
    FrameTreeMissingDataException,
    FrameTreeUsageError,
    DatatypeUnsupportedByStoreError,
)
from frametree.core.utils import get_home_dir, append_suffix
from ..row import DataRow
from ..entry import DataEntry
from .base import Store


logger = logging.getLogger("frametree")


# Matches directory names used for summary rows with dunder beginning and
# end (e.g. '__visit_01__') and hidden directories (i.e. starting with '.' or
# '~')
special_dir_re = re.compile(r"(__.*__$|\..*|~.*)")

DT = ty.TypeVar("DT", bound=DataType)


@attrs.define
class LocalStore(Store):
    """
    A Repository class for data stored hierarchically within sub-directories
    of a file-system directory. The depth and which layer in the data tree
    the sub-directories correspond to is defined by the `hierarchy` argument.

    Parameters
    ----------
    base_dir : str
        Path to the base directory of the "store", i.e. datasets are
        arranged by name as sub-directories of the base dir.

    """

    LOCK_SUFFIX = ".lock"
    FRAMETREE_DIR = "__frametree__"
    SITE_LICENSES_DIR = "site-licenses"

    name: str

    ##############################
    # Inherited abstract methods #
    ##############################

    # populate_tree

    # populate_row

    # put_provenance

    # get_provenance

    # create_data_tree

    ####################
    # Abstract methods #
    ####################

    @abstractmethod
    def get_field(self, entry: DataEntry, datatype: type) -> Field[ty.Any, ty.Any]:
        """Retrieves a field from a data entry

        Parameters
        ----------
        entry : DataEntry
            the entry to retrieve the file-set from
        datatype : type
            the type of the field from

        Returns
        -------
        Field
            the retrieved field
        """

    @abstractmethod
    def put_fileset(self, fileset: FileSet, entry: DataEntry) -> FileSet:
        """Stores a file-set into a data entry

        Parameters
        ----------
        fileset : FileSet
            the file-set to store
        entry : DataEntry
            the entry to store the file-set in

        Returns
        -------
        FileSet
            the file-set within the store
        """

    @abstractmethod
    def get_fileset(self, entry: DataEntry, datatype: type) -> FileSet:
        """Retrieves a file-set from a data entry

        Parameters
        ----------
        entry : DataEntry
            the entry to retrieve the file-set from
        datatype : type
            the type of the file-set

        Returns
        -------
        FileSet
            the retrieved file-set
        """

    @abstractmethod
    def put_field(self, field: Field[ty.Any, ty.Any], entry: DataEntry) -> None:
        """Stores a field into a data entry

        Parameters
        ----------
        field : Field
            the field to store
        entry : DataEntry
            the entry to store the field in
        """

    @abstractmethod
    def fileset_uri(self, path: str, datatype: type, row: DataRow) -> str:
        """Returns the "uri" (e.g. file-system path relative to root dir) of a file-set
        entry at the given path relative to the given row

        Parameters
        ----------
        path : str
            path to the entry relative to the row
        datatype : type
            the datatype of the entry
        row : DataRow
            the row of the entry

        Returns
        -------
        uri : str
            the "uri" to the file-set entry relative to the data store
        """

    @abstractmethod
    def field_uri(self, path: str, datatype: type, row: DataRow) -> str:
        """Returns the "uri" (e.g. file-system path relative to root dir) of a field
        entry at the given path relative to the given row

        Parameters
        ----------
        path : str
            path to the entry relative to the row
        datatype : type
            the datatype of the entry
        row : DataRow
            the row of the entry

        Returns
        -------
        uri : str
            the "uri" to the field entry relative to the data store
        """

    @abstractmethod
    def get_fileset_provenance(
        self, entry: DataEntry
    ) -> ty.Union[ty.Dict[str, ty.Any], None]:
        """Retrieves provenance associated with a file-set data entry

        Parameters
        ----------
        entry : DataEntry
            the entry of the file-set to retrieve the provenance for

        Returns
        -------
        ty.Dict[str, ty.Any] or None
            the retrieved provenance
        """

    @abstractmethod
    def put_fileset_provenance(
        self, provenance: ty.Dict[str, ty.Any], entry: DataEntry
    ) -> None:
        """Puts provenance associated with a file-set data entry into the store

        Parameters
        ----------
        provenance : dict[str, ty.Any]
            the provenance to store
        entry : DataEntry
            the entry to associate the proveance with
        """

    @abstractmethod
    def get_field_provenance(
        self, entry: DataEntry
    ) -> ty.Union[ty.Dict[str, ty.Any], None]:
        """Retrieves provenance associated with a field data entry

        Parameters
        ----------
        entry : DataEntry
            the entry of the field to retrieve the provenance for

        Returns
        -------
        ty.Dict[str, ty.Any] or None
            the retrieved provenance
        """

    @abstractmethod
    def put_field_provenance(
        self, provenance: ty.Dict[str, ty.Any], entry: DataEntry
    ) -> None:
        """Puts provenance associated with a field data entry into the store

        Parameters
        ----------
        provenance : dict[str, ty.Any]
            the provenance to store
        entry : DataEntry
            the entry to associate the proveance with
        """

    ##################################
    # Abstractmethod implementations #
    ##################################

    def connect(self) -> None:
        return None

    def disconnect(self, connection: ty.Any) -> None:
        pass

    def create_entry(self, path: str, datatype: type, row: DataRow) -> DataEntry:
        if issubclass(datatype, FileSet):
            uri = self.fileset_uri(path, datatype, row)
        else:
            uri = self.field_uri(path, datatype, row)
        return row.add_entry(path=path, datatype=datatype, uri=uri)

    def save_frameset_definition(
        self, dataset_id: str, definition: ty.Dict[str, ty.Any], name: str
    ) -> None:
        definition_path = self.definition_save_path(dataset_id, name)
        definition_path.parent.mkdir(exist_ok=True, parents=True)
        with open(definition_path, "w") as f:
            yaml.dump(definition, f)

    def load_frameset_definition(
        self, dataset_id: str, name: str
    ) -> ty.Dict[str, ty.Any]:
        fspath = self.definition_save_path(dataset_id, name)
        if fspath.exists():
            with open(fspath) as f:
                definition = yaml.load(f, Loader=yaml.Loader)
        else:
            definition = None
        return definition

    def get(self, entry: DataEntry, datatype: ty.Type[DT]) -> DT:
        if entry.datatype.is_fileset:
            item = self.get_fileset(entry, datatype)
        elif entry.datatype.is_field:
            item = self.get_field(entry, datatype)
        else:
            raise RuntimeError(
                f"Don't know how to retrieve {entry.datatype} data from {type(self)} stores"
            )
        return item

    def put(self, item: DT, entry: DataEntry) -> DT:
        if entry.datatype.is_fileset:
            cpy = self.put_fileset(item, entry)
        elif entry.datatype.is_field:
            cpy = self.put_field(item, entry)
        else:
            raise RuntimeError(
                f"Don't know how to store {entry.datatype} data in {type(self)} stores"
            )
        return cpy

    def get_provenance(self, entry: DataEntry) -> ty.Dict[str, ty.Any]:
        if entry.datatype.is_fileset:
            provenance = self.get_fileset_provenance(entry)
        elif entry.datatype.is_field:
            provenance = self.get_field_provenance(entry)
        else:
            raise DatatypeUnsupportedByStoreError(entry.datatype, self)
        return provenance

    def put_provenance(
        self, provenance: ty.Dict[str, ty.Any], entry: DataEntry
    ) -> None:
        if entry.datatype.is_fileset:
            self.put_fileset_provenance(provenance, entry)
        elif entry.datatype.is_field:
            self.put_field_provenance(provenance, entry)
        else:
            raise DatatypeUnsupportedByStoreError(entry.datatype, self)

    def root_dir(self, row: DataRow) -> Path:
        return Path(row.frameset.id)

    def site_licenses_dataset(self, **kwargs: ty.Any):
        """Provide a place to store hold site-wide licenses"""
        dataset_root = get_home_dir() / self.SITE_LICENSES_DIR
        if not dataset_root.exists():
            dataset_root.mkdir(parents=True)
        try:
            dataset = self.load_frameset(dataset_root)
        except KeyError:
            from frametree.common import Samples

            dataset = self.define_frameset(dataset_root, axes=Samples)
        return dataset

    ###################
    # Other overrides #
    ###################

    def define_frameset(self, id: str, *args: ty.Any, **kwargs: ty.Any):
        if not Path(id).exists():
            raise FrameTreeUsageError(f"Path to dataset root '{id}'' does not exist")
        return super().define_frameset(id, *args, **kwargs)

    ##################
    # Helper methods #
    ##################

    def update_json(self, fpath: Path, key: str, value: ty.Any) -> None:
        """Updates a JSON file in a multi-process safe way"""
        # Open fields JSON, locking to prevent other processes
        # reading or writing
        with InterProcessLock(append_suffix(fpath, self.LOCK_SUFFIX), logger=logger):
            try:
                with open(fpath) as f:
                    dct = json.load(f)
            except IOError as e:
                if e.errno == errno.ENOENT:
                    dct = {}
                else:
                    raise
            dct[key] = value
            with open(fpath, "w") as f:
                json.dump(dct, f, indent=4)

    def read_from_json(self, fpath: Path, key: str) -> ty.Any:
        """
        Load fields JSON, locking to prevent read/write conflicts
        Would be better if only checked if locked to allow
        concurrent reads but not possible with multi-process
        locks (in my understanding at least).
        """
        try:
            with InterProcessLock(
                append_suffix(fpath, self.LOCK_SUFFIX), logger=logger
            ), open(fpath, "r") as f:
                dct = json.load(f)
            return dct[key]
        except (KeyError, IOError) as e:
            try:
                # Check to see if the IOError wasn't just because of a
                # missing file
                if e.errno != errno.ENOENT:
                    raise
            except AttributeError:
                pass
            raise FrameTreeMissingDataException(
                "{} does not exist in the local store {}".format(key, self)
            )

    def definition_save_path(self, dataset_id: str, name: str) -> Path:
        if not name:
            name = "_"
        return Path(dataset_id) / self.FRAMETREE_DIR / name / "definition.yaml"
