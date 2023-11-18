"""Initialisation of the PyBispectra package."""

__version__ = "1.1.0"

from .cfc import AAC, PAC, PPC
from .tde import TDE
from .waveshape import WaveShape
from .utils import (
    ResultsCFC,
    ResultsTDE,
    ResultsWaveShape,
    SpatioSpectralFilter,
    compute_fft,
    compute_tfr,
    compute_rank,
    set_precision,
)
from .data import get_example_data_paths
