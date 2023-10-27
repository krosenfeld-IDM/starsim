""" 
stisim distributions

Example usage

>>> dist = stisim.normal(1,1) # Make a distribution
>>> dist()  # Draw a sample
>>> dist(10) # Draw several samples
>>> dist.sample(10) # Same as above
>>> stisim.State('foo', float, fill_value=dist)  # Use distribution as the fill value for a state
>>> disease.pars['immunity'] = dist  # Store the distribution as a parameter
>>> disease.pars['immunity'].sample(5)  # Draw some samples from the parameter
>>> stisim.poisson(rate=1).sample(n=10)  # Sample from a temporary distribution
"""

import numpy as np
import sciris as sc
from .utils import get_subclasses

__all__ = [
    'Distribution', 'bernoulli', 'uniform', 'choice', 'normal', 'normal_pos', 'normal_int', 'lognormal', 'lognormal_int',
    'poisson', 'neg_binomial', 'beta', 'gamma', 'data_dist'
]




class Distribution():

    def __init__(self, rng=None):
        if rng is None:
            self.stream = np.random.default_rng() # Default to centralized random number generator
        else:
            self.stream = rng
        return

    def set_stream(self, stream):
        """
        Switch to a user-supplied random number stream
        """
        self.stream = stream
        return

    def mean(self):
        """
        Return the mean value
        """
        raise NotImplementedError

    def __call__(self, size=None, uids=None, **kwargs):
        return self.sample(size=size, uids=uids, **kwargs)

    @property
    def name(self):
        return self.__class__.__name__

    def sample(cls, size=None, uids=None, **kwargs):
        """
        Return a specified number of samples from the distribution
        """
        raise NotImplementedError

    @classmethod
    def create(cls, name, *args, **kwargs):
        """
        Create a distribution instance by name

        :param name: A string with the name of a distribution class e.g., 'normal'
        :param args:
        :param kwargs:
        :return:
        """
        for subcls in get_subclasses(cls):
            if subcls.__name__ == name:
                return subcls(*args, **kwargs)
        else:
            raise KeyError(f'Distribution "{name}" did not match any known distributions')


class data_dist(Distribution):
    """ Sample from data """

    def __init__(self, vals, bins, **kwargs):
        super().__init__(**kwargs)
        self.vals = vals
        self.bins = bins

    def mean(self):
        return

    def sample(self, size, **kwargs):
        """ Sample using CDF """
        bin_midpoints = self.bins[:-1] + np.diff(self.bins) / 2
        cdf = np.cumsum(self.vals)
        cdf = cdf / cdf[-1]
        values = self.stream.rand(size)
        value_bins = np.searchsorted(cdf, values)
        return bin_midpoints[value_bins]


class uniform(Distribution):
    """
    Uniform distribution
    """

    def __init__(self, low, high, **kwargs):
        super().__init__(**kwargs)
        self.low = low
        self.high = high

    def mean(self):
        return (self.low + self.high) / 2

    def sample(self, **kwargs):
        return self.stream.uniform(low=self.low, high=self.high, **kwargs)

class bernoulli(Distribution):
    """
    Bernoulli distribution, returns sequence of True or False from independent trials
    """

    def __init__(self, p, **kwargs):
        super().__init__(**kwargs)
        self.p = p

    def mean(self):
        return self.p

    def sample(self, **kwargs):
        return self.stream.bernoulli(prob=self.p, **kwargs)


class choice(Distribution):
    """
    Choose from samples, optionally with specific probabilities
    """

    def __init__(self, choices, probabilities=None, replace=True, **kwargs):
        super().__init__(**kwargs)
        self.choices = choices
        self.probabilities = probabilities
        self.replace = replace

    def sample(self, **kwargs):
        return self.stream.choice(a=self.choices, p=self.probabilities, replace=self.replace, **kwargs)


class normal(Distribution):
    """
    Normal distribution
    """

    def __init__(self, mean, std, **kwargs):
        super().__init__(**kwargs)
        self.mean = mean
        self.std = std

    def sample(self, **kwargs):
        return self.stream.normal(loc=self.mean, scale=self.std, **kwargs)


class normal_pos(normal):
    """
    right-sided normal (i.e. only +ve values), with mean=par1, std=par2 of the underlying normal

    WARNING - this function came from hpvsim but confirm that the implementation is correct?
    """

    def sample(self, **kwargs):
        return np.abs(super().sample(**kwargs))


class normal_int(normal):
    """
    Normal distribution returning only integer values
    """

    def sample(self, **kwargs):
        return np.round(super().sample(**kwargs))


class lognormal(Distribution):
    """
    lognormal with mean=par1, std=par2 (parameters are for the lognormal, not the underlying normal)

    Lognormal distributions are parameterized with reference to the underlying normal distribution (see:
    https://docs.scipy.org/doc/numpy-1.14.0/reference/generated/numpy.random.lognormal.html), but this
    function assumes the user wants to specify the mean and std of the lognormal distribution.
    """

    def __init__(self, mean, std, **kwargs):
        super().__init__(**kwargs)
        self.mean = mean
        self.std = std
        self.underlying_mean = np.log(mean ** 2 / np.sqrt(std ** 2 + mean ** 2))  # Computes the mean of the underlying normal distribution
        self.underlying_std = np.sqrt(np.log(std ** 2 / mean ** 2 + 1))  # Computes sigma for the underlying normal distribution
        return

    def sample(self, **kwargs):

        if (sc.isnumber(self.mean) and self.mean > 0) or (sc.checktype(self.mean, 'arraylike') and (self.mean > 0).all()):
            return self.stream.lognormal(mean=self.underlying_mean, sigma=self.underlying_std, **kwargs)
        
        if 'size' in kwargs:
            return np.zeros(kwargs['size'])
        elif 'uids' in kwargs:
            return np.zeros(len(kwargs['uids']))
        else:
            raise Exception('When calling sample(), please provide either "size" or "uids".')


class lognormal_int(lognormal):
    """
    Lognormal returning only integer values
    """

    def sample(self, **kwargs):
        return np.round(super().sample(**kwargs))


class poisson(Distribution):
    """
    Poisson distribution
    """

    def __init__(self, rate, **kwargs):
        super().__init__(**kwargs)
        self.rate = rate

    def mean(self):
        return self.rate

    def sample(self, **kwargs):
        return self.stream.poisson(self.rate, **kwargs)


class neg_binomial(Distribution):
    """
    Negative binomial distribution

    Negative binomial distributions are parameterized with reference to the mean and dispersion parameter k
    (see: https://en.wikipedia.org/wiki/Negative_binomial_distribution). The r parameter of the underlying
    distribution is then calculated from the desired mean and k. For a small mean (~1), a dispersion parameter
    of ∞ corresponds to the variance and standard deviation being equal to the mean (i.e., Poisson). For a
    large mean (e.g. >100), a dispersion parameter of 1 corresponds to the standard deviation being equal to
    the mean.
    """

    def __init__(self, mean, dispersion, **kwargs):
        """
        mean (float): the rate of the process (same as Poisson)
        dispersion (float):  dispersion parameter; lower is more dispersion, i.e. 0 = infinite, ∞ = Poisson
        n (int): number of trials
        """
        super().__init__(**kwargs)
        self.mean = mean
        self.dispersion = dispersion

    def sample(self, **kwargs):
        nbn_n = self.dispersion
        nbn_p = self.dispersion / (self.mean + self.dispersion)
        return self.stream.negative_binomial(n=nbn_n, p=nbn_p, **kwargs)


class beta(Distribution):
    """
    Beta distribution
    """

    def __init__(self, alpha, beta, **kwargs):
        super().__init__(**kwargs)
        self.alpha = alpha
        self.beta = beta

    def mean(self):
        return self.alpha / (self.alpha + self.beta)

    def sample(self, **kwargs):
        return self.stream.beta(a=self.alpha, b=self.beta, **kwargs)


class gamma(Distribution):
    """
    Gamma distribution
    """

    def __init__(self, shape, scale, **kwargs):
        super().__init__(**kwargs)
        self.shape = shape
        self.scale = scale

    def mean(self):
        return self.shape * self.scale

    def sample(self, **kwargs):
        return self.stream.gamma(shape=self.shape, scale=self.scale, **kwargs)