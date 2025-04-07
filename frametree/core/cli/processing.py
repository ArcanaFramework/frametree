from pathlib import Path
import logging
import typing as ty
import cloudpickle as cp
import click
import pydra.compose.base
from fileformats.core import from_mime
from frametree.core.frameset.base import FrameSet
from frametree.core.store import Store
from frametree.core.serialize import ClassResolver, parse_value
from frametree.core.utils import set_loggers
from .base import cli


logger = logging.getLogger("frametree")


@cli.command(
    name="derive",
    help="""Derive data for a data sink column and all prerequisite columns.

ADDRESS string containing the nickname of the data store, the ID of the dataset
(e.g. XNAT project ID or file-system directory) and the dataset's name in the
format <store-nickname>//<dataset-id>[@<dataset-name>]

COLUMNS are the names of the sink columns to derive""",
)
@click.argument("address")
@click.argument("columns", nargs=-1)
@click.option(
    "--work",
    "-w",
    default=None,
    help=(
        "The location of the directory where the working files "
        "created during the pipeline execution will be stored"
    ),
)
@click.option(
    "--plugin",
    default="cf",
    help=("The Pydra plugin with which to process the workflow"),
)
@click.option(
    "--loglevel",
    type=str,
    default="info",
    help=("The level of detail logging information is presented"),
)
def derive(address, columns, work, plugin, loglevel):

    logging.basicConfig(level=getattr(logging, loglevel.upper()))

    if work is not None:
        work_dir = Path(work)
        store_cache = work_dir / "store-cache"
        pipeline_cache = work_dir / "pipeline-cache"
    else:
        store_cache = None
        pipeline_cache = None

    dataset = FrameSet.load(address, cache_dir=store_cache)

    set_loggers(loglevel)

    dataset.derive(*columns, cache_dir=pipeline_cache, worker=plugin)

    columns_str = "', '".join(columns)
    logger.info(f"Derived data for '{columns_str}' column(s) successfully")


@cli.command(help="""Display the potential derivatives that can be derived""")
def menu():
    raise NotImplementedError


@cli.command(
    name="show-errors",
    help="""Show a Pydra crash report

NODE_WORK_DIR is the directory containing the error pickle file""",
)
@click.argument("node_work_dir")
def show_errors(node_work_dir):
    node_work_dir = Path(node_work_dir)
    files = ["_task.pklz", "_result.pklz", "_error.pklz"]  #
    for fname in files:
        fpath = node_work_dir / fname
        if fpath.exists():
            with open(fpath, "rb") as f:
                contents = cp.load(f)
            click.echo(f"{fname}:")
            if isinstance(contents, dict):
                for k, v in contents.items():
                    if k == "error message":
                        click.echo(f"{k}:\n" + "".join(v))
                    else:
                        click.echo(f"{k}: {v}")
            else:
                click.echo(contents)


@cli.command(
    name="ignore-diff",
    help="""Ignore difference between provenance of previously generated derivative
and new parameterisation""",
)
def ignore_diff():
    raise NotImplementedError


if __name__ == "__main__":
    from click.testing import CliRunner

    runner = CliRunner()
    runner.invoke(
        show_errors,
        [
            (
                "/Users/tclose/Downloads/892d1907-fe2b-40ac-9b77-a3f2ee21ca76/pipeline-cache/"
                "Workflow_f3a2bb7474848840aec86fd87e88f5938217fae5976fc699bfc993d95d48a3b8"
            )
        ],
        catch_exceptions=False,
    )


@cli.command(
    name="apply",
    help="""Apply a Pydra workflow to a dataset as a pipeline between
two columns

ADDRESS string containing the nickname of the data store, the ID of the dataset
(e.g. XNAT project ID or file-system directory) and the dataset's name in the
format <store-nickname>//<dataset-id>[@<dataset-name>]

PIPELINE_NAME is the name of the pipeline

WORKFLOW_LOCATION is the location to a Pydra workflow on the Python system path,
<MODULE>:<WORKFLOW>""",
)
@click.argument("address")
@click.argument("pipeline_name")
@click.argument("workflow_location")
@click.option(
    "--input",
    "-i",
    nargs=3,
    default=(),
    metavar="<col-name> <pydra-field> <required-datatype>",
    multiple=True,
    type=str,
    help=(
        "the link between a column and an input of the workflow. "
        "The required format is the location (<module-path>:<class>) of the format "
        "expected by the workflow"
    ),
)
@click.option(
    "--output",
    "-o",
    nargs=3,
    default=(),
    metavar="<col-name> <pydra-field> <produced-datatype>",
    multiple=True,
    type=str,
    help=(
        "the link between an output of the workflow and a sink column. "
        "The produced datatype is the location (<module-path>:<class>) of the datatype "
        "produced by the workflow"
    ),
)
@click.option(
    "--parameter",
    "-p",
    nargs=2,
    default=(),
    metavar="<name> <value>",
    multiple=True,
    type=str,
    help=("a fixed parameter of the workflow to set when applying it"),
)
@click.option(
    "--source",
    "-s",
    nargs=3,
    default=(),
    metavar="<col-name> <pydra-field> <required-datatype>",
    multiple=True,
    type=str,
    help=(
        "add a source to the dataset and link it to an input of the workflow "
        "in a single step. The source column must be able to be specified by its "
        "path alone and be already in the datatype required by the workflow"
    ),
)
@click.option(
    "--sink",
    "-k",
    nargs=3,
    default=(),
    metavar="<col-name> <pydra-field> <produced-datatype>",
    multiple=True,
    type=str,
    help=(
        "add a sink to the dataset and link it to an output of the workflow "
        "in a single step. The sink column be in the same datatype as produced "
        "by the workflow"
    ),
)
@click.option(
    "--row-frequency",
    "-f",
    default=None,
    type=str,
    help=(
        "the row-frequency of the rows the pipeline will be executed over, i.e. "
        "will it be run once per-session, per-subject or per whole dataset, "
        "by default the highest row-frequency rows (e.g. per-session)"
    ),
)
@click.option(
    "--overwrite/--no-overwrite",
    default=False,
    help=("whether to overwrite previous pipelines"),
)
def apply(
    address,
    pipeline_name,
    workflow_location,
    input,
    output,
    parameter,
    source,
    sink,
    row_frequency,
    overwrite,
):

    frameset = FrameSet.load(address)
    workflow = ClassResolver(pydra.compose.base.Task, alternative_types=[ty.Callable])(
        workflow_location
    )(**{n: parse_value(v) for n, v in parameter})

    inputs = parse_col_option(input)
    outputs = parse_col_option(output)
    sources = parse_col_option(source)
    sinks = parse_col_option(sink)

    for col_name, field, datatype in sources:
        frameset.add_source(col_name, datatype)
        inputs.append((col_name, field, datatype))

    for col_name, field, datatype in sinks:
        frameset.add_sink(col_name, datatype)
        outputs.append((col_name, field, datatype))

    frameset.apply(
        pipeline_name,
        workflow,
        inputs,
        outputs,
        row_frequency=row_frequency,
        overwrite=overwrite,
    )

    frameset.save()


def parse_col_option(option):
    return [(c, p, from_mime(f)) for c, p, f in option]


@cli.command(
    name="install-license",
    help="""Installs a license within a store (i.e. site-wide) or dataset (project-specific)
for use in a deployment pipeline

LICENSE_NAME the name of the license to upload. Must match the name of the license specified
in the deployment specification

SOURCE_FILE path to the license file to upload

INSTALL_LOCATIONS a list of installation locations, which are either the "nickname" of a
store (as saved by `frametree store add`) or the ID of a dataset in form
<store-nickname>//<dataset-id>[@<dataset-name>], where the dataset ID
is either the location of the root directory (for file-system based stores) or the
project ID for managed data repositories.
""",
)
@click.argument("license_name")
@click.argument("source_file", type=click.Path(exists=True, path_type=Path))
@click.argument("install_locations", nargs=-1)
@click.option(
    "--logfile",
    default=None,
    type=click.Path(path_type=Path),
    help="Log output to file instead of stdout",
)
@click.option("--loglevel", default="info", help="The level to display logs at")
def install_license(install_locations, license_name, source_file, logfile, loglevel):
    logging.basicConfig(filename=logfile, level=getattr(logging, loglevel.upper()))

    if isinstance(source_file, bytes):  # FIXME: This shouldn't be necessary
        source_file = Path(source_file.decode("utf-8"))

    if not install_locations:
        install_locations = ["file_system"]

    for install_loc in install_locations:
        if "//" in install_loc:
            dataset = FrameSet.load(install_loc)
            store_name, _, _ = FrameSet.parse_id_str(install_loc)
            msg = f"for '{dataset.name}' dataset on {store_name} store"
        else:
            store = Store.load(install_loc)
            dataset = store.site_licenses_dataset()
            if dataset is None:
                raise ValueError(
                    f"{install_loc} store doesn't support the installation of site-wide "
                    "licenses, please specify a dataset to install it for"
                )
            msg = f"site-wide on {install_loc} store"

        dataset.install_license(license_name, source_file)
        logger.info("Successfully installed '%s' license %s", license_name, msg)
