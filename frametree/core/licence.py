from urllib.parse import urlparse
from pathlib import Path, PurePath
import attrs


@attrs.define
class License:
    """Specification of a software license that needs to be present in the container
    when the command is run.

    Parameters
    ----------
    name : str
        a name to refer to the license with. Must be unique among the licenses used
        pipelines applied to a dataset, ideally for a site. Typically named closely
        after the package it is used for along with a version number if the license,
        needs to be updated with new versions e.g. freesurfer, fsl, matlab_v2022a etc...
    destination : PurePath
        destination within the container to install the license
    description : str
        a short description of the license and what it is used for
    info_url : str
        link to website with information about license, particularly how to download it
    source : Path, optional
        path to the location of a valid license file
    store_in_image : bool
        whether the license can be stored in the image or not according to the license
        conditions
    """

    name: str = attrs.field()
    destination: PurePath = attrs.field(converter=PurePath)
    description: str = attrs.field()
    info_url: str = attrs.field()
    source: Path = attrs.field(
        default=None, converter=lambda x: Path(x) if x is not None else None
    )
    store_in_image: bool = False

    @info_url.validator
    def info_url_validator(self, _, info_url):
        parsed = urlparse(info_url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(
                f"Could not parse info url '{info_url}', please include URL scheme"
            )

    # FIXME: this doesn't work inside images
    # @source.validator
    # def source_validator(self, _, source):
    #     if source is not None and not source.exists():
    #         raise ValueError(
    #             f"Source file for {self.name} license, '{str(source)}', does not exist"
    #         )

    @classmethod
    def column_path(self, name):
        """The column name (and resource name) for the license if it is to be downloaded
        from the source dataset"""
        return name + self.COLUMN_SUFFIX + "@"

    COLUMN_SUFFIX = "_LICENSE"
