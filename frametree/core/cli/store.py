from operator import itemgetter
import click
from frametree.core.store import Store
from frametree.core.serialize import ClassResolver
from frametree.core.utils import get_home_dir
from frametree.core.exceptions import FrameTreeUsageError
from .base import cli


@cli.group()
def store():
    pass


@store.command(
    help="""Saves the details for a new data store in the configuration file ('~/.frametree/stores.yaml').

TYPE of the storage class, typically the name of the package the type is defined, e.g. 'xnat'
or 'bids'. More specific types can be given by using a colon to separate the package name and
type, e.g. frametree.xnat:XnatViaCS

NAME The name the store will be saved as in the configuration file. This is used to refer to the
store when using the frametree CLI.
"""
)
@click.argument("type")
@click.argument("name")
@click.option(
    "--server",
    "-s",
    default=None,
    help="The URI of the server to connect to (if applicable)",
)
@click.option(
    "--user", "-u", default=None, help="The username to use to connect to the store"
)
@click.option(
    "--password",
    "-p",
    prompt=True,
    hide_input=True,
    help="The password to use to connect to the store",
)
@click.option(
    "--cache",
    "-c",
    default=None,
    help="The location of a cache dir to download local copies of remote data",
)
@click.option(
    "--race-condition-delay",
    "-d",
    type=int,
    help=(
        "How long to wait for changes on a incomplete download before assuming it has "
        "been interrupted, clearing it and starting again"
    ),
)
@click.option(
    "--option",
    "-o",
    nargs=2,
    multiple=True,
    metavar="<name> <value>",
    default=None,
    help="Additional key-word arguments that are passed to the store class",
)
def add(type, name, option, cache, **kwargs):
    if option is not None:
        options = dict(option)
        conflicting = set(options) & set(kwargs)
        if conflicting:
            raise FrameTreeUsageError(
                f"Custom options {conflicting} conflict with in-built options, please "
                "use them instead"
            )
        kwargs.update(options)
    store_cls = ClassResolver(Store)(type)
    if hasattr(store_cls, "cache_dir"):
        if cache is None:
            cache = get_home_dir() / "cache" / name
        cache.mkdir(parents=True, exist_ok=True)
        kwargs["cache_dir"] = cache
    store = store_cls(name=name, **kwargs)
    store.save(name)


@store.command(
    help="""
Renames a store in the configuration file

OLD_KNAME The current name of the store.

NEW_NAME The new name for the store.
"""
)
@click.argument("old_name")
@click.argument("new_name")
def rename(old_name, new_name):
    Store.load(old_name).save(new_name)
    Store.remove(old_name)


@store.command(
    help="""Remove a saved data store from the config file

NAME The name the store was given when its details were saved
"""
)
@click.argument("name")
def remove(name):
    Store.remove(name)


@store.command(
    help="""Refreshes credentials saved for the given store (typically a token that expires)

NAME The name the store was given when its details were saved
"""
)
@click.argument("name")
@click.option(
    "--user", "-u", default=None, help="The username to use to connect to the store"
)
@click.option(
    "--password",
    "-p",
    prompt=True,
    hide_input=True,
    help="The password to use to connect to the store",
)
def refresh(name, user, password):
    store = Store.load(name)
    if user is not None:
        store.user = user
    store.password = password
    store.save()
    Store.remove(name)
    store.save(name)


@store.command(help="""List available stores that have been saved""")
def ls():
    click.echo("Default stores\n---------------")
    for name, store in sorted(Store.singletons().items(), key=itemgetter(0)):
        click.echo(f"{name} - {ClassResolver.tostr(store, strip_prefix=False)}")
    click.echo("\nSaved stores\n-------------")
    for name, entry in Store.load_saved_configs().items():
        store_class = entry.pop("class")
        click.echo(f"{name} - {store_class[1:-1]}")
        for key, val in sorted(entry.items(), key=itemgetter(0)):
            click.echo(f"    {key}: {val}")
