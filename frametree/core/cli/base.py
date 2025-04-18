import click
import frametree.core as core


# Define the base CLI entrypoint
@click.group()
@click.version_option(version=core.__version__)
def cli():
    """Base command line group, installed as "frametree"."""
