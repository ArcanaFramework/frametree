import attrs
import pytest

from frametree.core.serialize import ObjectConverter


def test_construction_error_does_not_repr_unfinished_parent():
    class Unfinished:
        def __repr__(self):
            raise AttributeError("commands not constructed")

    @attrs.define
    class Broken:
        parent: object

        def __attrs_post_init__(self):
            raise TypeError("unsupported input type")

    with pytest.raises(TypeError, match="unsupported input type") as caught:
        ObjectConverter(Broken)({"parent": Unfinished()})

    assert any("parent" in note for note in caught.value.__notes__)
