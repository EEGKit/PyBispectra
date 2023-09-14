"""Tools for handling AAC analysis."""

from copy import deepcopy

import numpy as np
from numba import njit
from pqdm.processes import pqdm

from pybispectra.utils import ResultsCFC
from pybispectra.utils._process import _ProcessFreqBase
from pybispectra.utils._utils import _compute_pearsonr_2d, _fast_find_first


class AAC(_ProcessFreqBase):
    """Class for computing amplitude-amplitude coupling (AAC).

    Parameters
    ----------
    data : ~numpy.ndarray, shape of [epochs, channels, frequencies, times]
        Amplitude (power) of the time-frequency representation of data.

    freqs : ~numpy.ndarray, shape of [frequencies]
        Frequencies (in Hz) in :attr:`data`.

    sampling_freq : int | float
        Sampling frequency (in Hz) of :attr:`data`.

    verbose : bool (default True)
        Whether or not to report the progress of the processing.

    Methods
    -------
    compute :
        Compute AAC, averaged over epochs.

    copy :
        Return a copy of the object.

    Attributes
    ----------
    results : tuple of ~pybispectra.utils.ResultsCFC
        AAC results.

    data : ~numpy.ndarray, shape of [epochs, channels, frequencies, times]
        Amplitude (power) of the time-frequency representation of data.

    freqs : ~numpy.ndarray, shape of [frequencies]
        Frequencies (in Hz) in :attr:`data`.

    sampling_freq : int | float
        Sampling frequency (in Hz) of :attr:`data`.

    indices : tuple of list of int, length of 2
        Indices of the seed and target channels, respectively, most recently
        used with :meth:`compute`.

    f1s : ~numpy.ndarray, shape of [frequencies]
        Low frequencies (in Hz) most recently used with :meth:`compute`.

    f2s : ~numpy.ndarray, shape of [frequencies]
        High frequencies (in Hz) most recently used with :meth:`compute`.

    verbose : bool
        Whether or not to report the progress of the processing.
    """  # noqa E501

    _data_ndims = 4  # [epochs, channels, frequencies, times]

    _aac = None

    def compute(
        self,
        indices: tuple[list[int], list[int]] | None = None,
        f1s: np.ndarray | None = None,
        f2s: np.ndarray | None = None,
        n_jobs: int = 1,
    ) -> None:
        r"""Compute AAC across epochs.

        Parameters
        ----------
        indices : tuple of list of int, length of 2 | None (default None)
            Indices of the seed and target channels, respectively, to compute
            AAC between. If :obj:`None`, coupling between all channels is
            computed.

        f1s : ~numpy.ndarray | None (default None), shape of [frequencies]
            Lower frequencies to compute AAC on. If :obj:`None`, all
            frequencies are used.

        f2s : ~numpy.ndarray | None (default None), shape of [frequencies]
            Higher frequencies to compute AAC on. If :obj:`None`, all
            frequencies are used.

        n_jobs : int (default ``1``)
            Number of jobs to run in parallel. If ``-1``, all available CPUs
            are used.

        Notes
        -----
        AAC is computed as the Pearson correlation coefficient across times for
        each frequency in each epoch, with coupling being averaged across
        epochs :footcite:`Giehl2021`.

        AAC is computed between all values of :attr:`f1s` and :attr:`f2s`. If
        any value of :attr:`f1s` is higher than :attr:`f2s`, a :obj:`numpy.nan`
        value is returned.

        References
        ----------
        .. footbibliography::
        """  # noqa E501
        self._reset_attrs()

        self._sort_indices(indices)
        self._sort_freqs(f1s, f2s)
        self._sort_parallelisation(n_jobs)

        if self.verbose:
            print("Computing AAC...")

        self._compute_aac()
        self._store_results()

        if self.verbose:
            print("    ... AAC computation finished\n")

    def _reset_attrs(self) -> None:
        """Reset attrs. of the object to prevent interference."""
        super()._reset_attrs()
        self._aac = None

    def _compute_aac(self) -> None:
        """Compute AAC between f1s of seeds and f2s of targets."""
        args = [
            {
                "data": self.data[:, (seed, target)],
                "freqs": self.freqs,
                "f1s": self.f1s,
                "f2s": self.f2s,
            }
            for seed, target in zip(self._seeds, self._targets)
        ]

        self._aac = np.array(
            pqdm(
                args,
                _compute_aac,
                self._n_jobs,
                argument_type="kwargs",
                desc="Processing connections...",
                disable=not self.verbose,
            )
        )

    def _store_results(self) -> None:
        """Store computed results in an object."""
        self._results = ResultsCFC(
            self._aac, self.indices, self.f1s, self.f2s, "AAC"
        )

    @property
    def results(self) -> ResultsCFC:
        """Return the results.

        Returns
        -------
        results : ~pybispectra.utils.ResultsCFC
            The results of the AAC computation.
        """
        return deepcopy(self._results)


@njit
def _compute_aac(
    data: np.ndarray,
    freqs: np.ndarray,
    f1s: np.ndarray,
    f2s: np.ndarray,
) -> np.ndarray:  # pragma: no cover
    """Compute AAC for a single connection across epochs.

    Parameters
    ----------
    data : numpy.ndarray, shape of [epochs, 2, frequencies, times]
        Amplitude (power) of the time-frequency representation of data where
        the second dimension contains the data for the seed and target channel
        of a single connection, respectively.

    freqs : numpy.ndarray, shape of [frequencies]
        Frequencies in ``data``.

    f1s : numpy.ndarray, shape of [frequencies]
        Low frequencies to compute coupling for.

    f2s : numpy.ndarray, shape of [frequencies]
        High frequencies to compute coupling for.

    Returns
    -------
    results : numpy.ndarray, shape of [f1s, f2s]
        AAC averaged across epochs for a single connection.
    """
    results = np.full(
        (f1s.shape[0], f2s.shape[0]), fill_value=np.nan, dtype=np.float64
    )
    f1_idx = 0  # starting index to find f1s
    for f1_i, f1 in enumerate(f1s):
        f2_idx = 0  # starting index to find f2s
        for f2_i, f2 in enumerate(f2s):
            if f1 <= f2 and f1 > 0:
                f1_idx = _fast_find_first(freqs, f1, f1_idx)
                f2_idx = _fast_find_first(freqs, f2, f2_idx)

                results[f1_i, f2_i] = np.mean(
                    _compute_pearsonr_2d(
                        data[:, 0, f1_idx], data[:, 1, f2_idx]
                    )
                )

    return results
