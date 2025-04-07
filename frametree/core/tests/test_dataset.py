from pathlib import Path
import cloudpickle as cp
from pydra.compose import python, workflow
from pydra.engine.job import Job
from pydra.engine.submitter import Submitter
from pydra.utils.hash import hash_object
from frametree.core.frameset.base import FrameSet
from frametree.core.serialize import asdict, fromdict


def test_dataset_asdict_roundtrip(dataset):

    dct = asdict(dataset, omit=["store", "id"])
    undct = fromdict(dct, store=dataset.store, id=dataset.id)
    assert isinstance(dct, dict)
    assert "store" not in dct
    del dataset.__annotations__["blueprint"]
    assert dataset == undct


def test_dataset_pickle(dataset: FrameSet, tmp_dir: Path):
    fpath = tmp_dir / "dataset.pkl"
    with fpath.open("wb") as fp:
        cp.dump(dataset, fp)
    with fpath.open("rb") as fp:
        reloaded = cp.load(fp)
    assert dataset == reloaded


def test_dataset_in_workflow_pickle(dataset: FrameSet, tmp_dir: Path):

    # Create the outer workflow to link the analysis workflow with the
    # data row iteration and store connection rows
    @workflow.define(outputs={"c": int})
    def Workflow(a):

        test_func = workflow.add(func(a=wf.lzin.a, b=2, dataset=dataset))

        return test_func.c

    job = Job(
        task=Workflow(a=1),
        submitter=Submitter(),
        name="job",
    )

    job.pickle_task()


@python.define(outputs=["c"])
def func(a: int, b: int, dataset: FrameSet) -> int:
    return a + b


def test_dataset_bytes_hash(dataset):

    hsh = hash_object(dataset)
    # Check hashing is stable
    assert hash_object(dataset) == hsh
