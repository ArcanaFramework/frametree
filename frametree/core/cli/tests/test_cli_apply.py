from frametree.core.grid.base import Grid
from fileformats.text import TextFile
from frametree.core.cli.apply import apply_pipeline
from frametree.core.utils import show_cli_trace


def test_apply_pipeline_cli(saved_dataset: Grid, concatenate_task, cli_runner):
    # Get CLI name for dataset (i.e. file system path prepended by 'file_system//')
    # Start generating the arguments for the CLI
    # Add source to loaded dataset
    duplicates = 5
    saved_dataset.add_source("file1", TextFile)
    saved_dataset.add_source("file2", TextFile)
    saved_dataset.add_sink("concatenated", TextFile)
    saved_dataset.apply_pipeline(
        name="a_pipeline",
        workflow=concatenate_task(name="workflow", duplicates=duplicates),
        inputs=[("file1", "in_file1"), ("file2", "in_file2")],
        outputs=[("concatenated", "out_file")],
    )
    # Add source column to saved dataset
    result = cli_runner(
        apply_pipeline,
        [
            saved_dataset.locator,
            "a_pipeline",
            "frametree.testing.tasks:" + concatenate_task.__name__,
            "--source",
            "file1",
            "in_file1",
            "text/text-file",
            "--source",
            "file2",
            "in_file2",
            "text/text-file",
            "--sink",
            "concatenated",
            "out_file",
            "text/text-file",
            "--parameter",
            "duplicates",
            str(duplicates),
        ],
    )
    assert result.exit_code == 0, show_cli_trace(result)
    loaded_dataset = Grid.load(saved_dataset.locator)
    assert saved_dataset.pipelines == loaded_dataset.pipelines
