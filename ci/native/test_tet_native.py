"""Low-level native-extension oracle; not PyVista/[all] acceptance."""
import importlib.metadata
import importlib.util
import os
from pathlib import Path
import numpy as np
import pytest

handles = []
dist = importlib.metadata.distribution('pytetwild')
for file in dist.files:
    if str(file).lower().endswith('.dll'):
        handles.append(os.add_dll_directory(str(Path(dist.locate_file(file)).parent)))
pyd = next(Path(dist.locate_file(f)) for f in dist.files if str(f).endswith('.pyd'))
spec = importlib.util.spec_from_file_location('PyfTetWildWrapper', pyd)
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


def test_native_unit_tetrahedron_volume_and_negative_control():
    vertices = np.array([[0,0,0],[1,0,0],[0,1,0],[0,0,1]], dtype=np.float64)
    faces = np.array([[0,2,1],[0,1,3],[0,3,2],[1,2,3]], dtype=np.uint32)
    points, cells = native.tetrahedralize_mesh(vertices, faces, True, False, 0.15, 0.0, 1e-3, 10.0, False, 2, 5, 6, True, False, False)
    assert points.ndim == 2 and points.shape[1] == 3
    assert cells.ndim == 2 and cells.shape[1] == 4 and len(cells) > 0
    assert np.isfinite(points).all()
    assert cells.min() >= 0 and cells.max() < len(points)
    q = points[cells]
    volumes = np.abs(np.linalg.det(q[:,1:]-q[:,:1])) / 6
    assert (volumes > 0).all()
    assert volumes.sum() == pytest.approx(1/6, rel=0.02)
    assert points.min() >= -0.01 and points.max() <= 1.01
    assert (points.sum(axis=1) <= 1.01).all()
    with pytest.raises(AssertionError):
        assert (volumes * 8).sum() == pytest.approx(1/6, rel=0.02)
