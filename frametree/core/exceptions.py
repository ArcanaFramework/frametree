class FrameTreeException(Exception):
    @property
    def msg(self):
        return self.args[0]

    @msg.setter
    def msg(self, msg):
        self.args = (msg,) + self.args[1:]


class FrametreeCannotSerializeDynamicDefinitionError(FrameTreeException):
    """
    Raised when a FrameTree object cannot be serialized
    """

    def __init__(self, msg: str):
        super().__init__(msg)
        self.msg = msg


class FrameTreeError(FrameTreeException):
    pass


class FrameTreeRuntimeError(FrameTreeError):
    pass


class FrameTreeNotBoundToAnalysisError(FrameTreeError):
    pass


class FrameTreeVersionError(FrameTreeError):
    pass


class FrameTreeRequirementNotFoundError(FrameTreeVersionError):
    pass


class FrameTreeVersionNotDetectableError(FrameTreeVersionError):
    pass


class FrameTreeEnvModuleNotLoadedError(FrameTreeError):
    pass


class FrameTreeMissingInputError(FrameTreeException):
    pass


class FrameTreeProtectedOutputConflictError(FrameTreeError):
    pass


class FrameTreeCantPickleAnalysisError(FrameTreeError):
    pass


class FrameTreeRepositoryError(FrameTreeError):
    pass


class FrameTreeUsageError(FrameTreeError):
    pass


class FrameTreeCacheError(FrameTreeError):
    pass


class FrameTreeDesignError(FrameTreeError):
    pass


class NamedFrameTreeError(FrameTreeError):
    def __init__(self, name: str, msg: str) -> None:
        super(NamedFrameTreeError, self).__init__(msg)
        self.name = name


class FrameTreeNameError(NamedFrameTreeError):
    pass


class FrameTreeWrongFrequencyError(NamedFrameTreeError):
    pass


class FrameTreeIndexError(FrameTreeError):
    def __init__(self, index: int, msg: str) -> None:
        super(FrameTreeIndexError, self).__init__(msg)
        self.index = index


class FrameTreeDataMatchError(FrameTreeUsageError):
    pass


class FrameTreePipelinesStackError(FrameTreeError):
    pass


class FrameTreeMissingDataException(FrameTreePipelinesStackError):
    pass


class FrameTreeOutputNotProducedException(FrameTreePipelinesStackError):
    """
    Raised when a given spec is not produced due to switches and inputs
    provided to the analysis
    """


class FrameTreeInsufficientRepoDepthError(FrameTreeError):
    pass


class FrameTreeLicenseNotFoundError(FrameTreeNameError):
    pass


class FrameTreeUnresolvableFormatException(FrameTreeException):
    pass


class FrameTreeFileSetNotCachedException(FrameTreeException):
    pass


class NoMatchingPipelineException(FrameTreeException):
    pass


class FrameTreeModulesError(FrameTreeError):
    pass


class FrameTreeModulesNotInstalledException(FrameTreeException):
    pass


class FrameTreeJobSubmittedException(FrameTreeException):
    """
    Signifies that a pipeline has been submitted to a scheduler and
    a return value won't be returned.
    """


class FrameTreeNoRunRequiredException(FrameTreeException):
    """
    Used to signify when a pipeline doesn't need to be run as all
    required outputs are already present in the store
    """


class FrameTreeFileFormatClashError(FrameTreeError):
    """
    Used when two mismatching data formats are registered with the same
    name or extension
    """


class FrameTreeConverterNotAvailableError(FrameTreeError):
    "The converter required to convert between formats is not"

    "available"


class FrameTreeReprocessException(FrameTreeException):
    pass


class FrameTreeWrongRepositoryError(FrameTreeError):
    pass


class FrameTreeIvalidParameterError(FrameTreeError):
    pass


class FrameTreeRequirementVersionsError(FrameTreeError):
    pass


class FrameTreeXnatCommandError(FrameTreeRepositoryError):
    """
    Error in the command file used to access an XNAT repository via the XNAT
    container service.
    """


class FrameTreeUriAlreadySetException(FrameTreeException):
    """Raised when attempting to set the URI of an item is already set"""


class FrameTreeConstructionError(FrameTreeError):
    "Error in constructing data tree by store find_rows method"


class FrameTreeBadlyFormattedIDError(FrameTreeConstructionError):
    "Error attempting to extract an ID from a tree path using a user provided regex"


class FrameTreeWrongAxesError(FrameTreeError):
    "Provided row_frequency is not a valid member of the dataset's dimensions"


class FrameTreeNoDirectXnatMountException(FrameTreeException):
    "Raised when attemptint to access a file-system mount for a row that hasn't been mounted directly"

    pass


class FrameTreeEmptyDatasetError(FrameTreeException):
    pass


class FrameTreeBuildError(FrameTreeError):
    pass


class NamedError(Exception):
    def __init__(self, name, msg):
        super().__init__(msg)
        self.name = name


class NameError(NamedError):
    pass


class DataNotDerivedYetError(NamedError):
    pass


class DatatypeUnsupportedByStoreError(FrameTreeError):
    """Raised when a data store doesn't support a given datatype"""

    def __init__(self, datatype, store):
        super().__init__(
            f"'{datatype.mime_like}' data types aren't supported by {type(store)} stores"
        )
