"""
Base classes for *sim models
"""

import numpy as np
import pandas as pd
import sciris as sc
import functools
from . import utils as ssu
from . import misc as ssm
from . import settings as sss
from .version import __version__

# Specify all externally visible classes this file defines
__all__ = ['ParsObj', 'BaseSim', 'State', 'StochState', 'BasePeople', 'FlexDict']

# Default object getter/setter
obj_set = object.__setattr__
base_key = 'uid'  # Define the key used by default for getting length, etc.


def rsetattr(obj, attr, val):
    pre, _, post = attr.rpartition('.')
    return setattr(rgetattr(obj, pre) if pre else obj, post, val)


def rgetattr(obj, attr, *args):
    def _getattr(obj, attr):
        return getattr(obj, attr, *args)

    return functools.reduce(_getattr, [obj] + attr.split('.'))


# %% Define simulation classes

class ParsObj(sc.prettyobj):
    """
    A class based around performing operations on a self.pars dict.
    """

    def __init__(self, pars, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.update_pars(pars, create=True)
        return

    def __getitem__(self, key):
        """ Allow sim['par_name'] instead of sim.pars['par_name'] """
        try:
            return self.pars[key]
        except:
            all_keys = '\n'.join(list(self.pars.keys()))
            errormsg = f'Key "{key}" not found; available keys:\n{all_keys}'
            raise sc.KeyNotFoundError(errormsg)

    def __setitem__(self, key, value):
        """ Ditto """
        if key in self.pars:
            self.pars[key] = value
        else:
            all_keys = '\n'.join(list(self.pars.keys()))
            errormsg = f'Key "{key}" not found; available keys:\n{all_keys}'
            raise sc.KeyNotFoundError(errormsg)
        return




def set_metadata(obj, **kwargs):
    """ Set standard metadata for an object """
    obj.created = kwargs.get('created', sc.now())
    obj.version = kwargs.get('version', __version__)
    obj.git_info = kwargs.get('git_info', ssm.git_info())
    return


class BaseSim(ParsObj):
    """
    The BaseSim class stores various methods useful for the Sim that are not directly
    related to simulating.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)  # Initialize and set the parameters as attributes

        return

    def _disp(self):
        """
        Print a verbose display of the sim object. Used by repr(). See sim.disp()
        for the user version. Equivalent to sc.prettyobj().
        """
        return sc.prepr(self)

    def update_pars(self, pars=None, create=False, **kwargs):
        """ Ensure that metaparameters get used properly before being updated """

        # Merge everything together
        pars = sc.mergedicts(pars, kwargs)
        if pars:
            self.pars.update_pars(pars=pars, create=create)

        return

    @property
    def n(self):
        """ Count the number of people -- if it fails, assume none """
        try:  # By default, the length of the people dict
            return len(self.people)
        except:  # pragma: no cover # If it's None or missing
            return 0

    def shrink(self, skip_attrs=None, in_place=True):
        """
        "Shrinks" the simulation by removing the people and other memory-intensive
        attributes (e.g., some interventions and analyzers), and returns a copy of
        the "shrunken" simulation. Used to reduce the memory required for RAM or
        for saved files.

        Args:
            skip_attrs (list): a list of attributes to skip (remove) in order to perform the shrinking; default "people"
            in_place (bool): whether to perform the shrinking in place (default), or return a shrunken copy instead

        Returns:
            shrunken (Sim): a Sim object with the listed attributes removed
        """
        # By default, skip people (~90% of memory), popdict, and _orig_pars (which is just a backup)
        if skip_attrs is None:
            skip_attrs = ['popdict', 'people', '_orig_pars']

        # Create the new object, and copy original dict, skipping the skipped attributes
        if in_place:
            shrunken = self
            for attr in skip_attrs:
                setattr(self, attr, None)
        else:
            shrunken = object.__new__(self.__class__)
            shrunken.__dict__ = {k: (v if k not in skip_attrs else None) for k, v in self.__dict__.items()}

        # Don't return if in place
        if in_place:
            return
        else:
            return shrunken

    def save(self, filename=None, keep_people=None, skip_attrs=None, **kwargs):
        """
        Save to disk as a gzipped pickle.

        Args:
            filename (str or None): the name or path of the file to save to; if None, uses stored
            keep_people (bool or None): whether to keep the people
            skip_attrs (list): attributes to skip saving
            kwargs: passed to sc.makefilepath()

        Returns:
            filename (str): the validated absolute path to the saved file

        **Example**::

            sim.save() # Saves to a .sim file
        """

        # Set keep_people based on whether we're in the middle of a run
        if keep_people is None:
            if self.initialized and not self.results_ready:
                keep_people = True
            else:
                keep_people = False

        # Handle the filename
        if filename is None:
            filename = self.simfile
        filename = sc.makefilepath(filename=filename, **kwargs)
        self.filename = filename  # Store the actual saved filename

        # Handle the shrinkage and save
        if skip_attrs or not keep_people:
            obj = self.shrink(skip_attrs=skip_attrs, in_place=False)
        else:
            obj = self
        ssm.save(filename=filename, obj=obj)

        return filename

    @staticmethod
    def load(filename, *args, **kwargs):
        """
        Load from disk from a gzipped pickle.
        """
        sim = ssm.load(filename, *args, **kwargs)
        if not isinstance(sim, BaseSim):  # pragma: no cover
            errormsg = f'Cannot load object of {type(sim)} as a Sim object'
            raise TypeError(errormsg)
        return sim

    def _get_ia(self, which, label=None, partial=False, as_list=False, as_inds=False, die=True, first=False):
        """ Helper method for get_interventions() and get_analyzers(); see get_interventions() docstring """

        # Handle inputs
        if which not in ['interventions', 'analyzers']:  # pragma: no cover
            errormsg = f'This method is only defined for interventions and analyzers, not "{which}"'
            raise ValueError(errormsg)

        ia_list = sc.tolist(
            self.analyzers if which == 'analyzers' else self.interventions)  # List of interventions or analyzers
        n_ia = len(ia_list)  # Number of interventions/analyzers

        if label == 'summary':  # Print a summary of the interventions
            df = pd.DataFrame(columns=['ind', 'label', 'type'])
            for ind, ia_obj in enumerate(ia_list):
                df = df.append(dict(ind=ind, label=str(ia_obj.label), type=type(ia_obj)), ignore_index=True)
            print(f'Summary of {which}:')
            print(df)
            return

        else:  # Standard usage case
            position = 0 if first else -1  # Choose either the first or last element
            if label is None:  # Get all interventions if no label is supplied, e.g. sim.get_interventions()
                label = np.arange(n_ia)
            if isinstance(label, np.ndarray):  # Allow arrays to be provided
                label = label.tolist()
            labels = sc.promotetolist(label)

            # Calculate the matches
            matches = []
            match_inds = []
            for label in labels:
                if sc.isnumber(label):
                    matches.append(ia_list[label])  # This will raise an exception if an invalid index is given
                    label = n_ia + label if label < 0 else label  # Convert to a positive number
                    match_inds.append(label)
                elif sc.isstring(label) or isinstance(label, type):
                    for ind, ia_obj in enumerate(ia_list):
                        if sc.isstring(label) and ia_obj.label == label or (partial and (label in str(ia_obj.label))):
                            matches.append(ia_obj)
                            match_inds.append(ind)
                        elif isinstance(label, type) and isinstance(ia_obj, label):
                            matches.append(ia_obj)
                            match_inds.append(ind)
                else:  # pragma: no cover
                    errormsg = f'Could not interpret label type "{type(label)}": should be str, int, list, or {which} class'
                    raise TypeError(errormsg)

            # Parse the output options
            if as_inds:
                output = match_inds
            elif as_list:  # Used by get_interventions()
                output = matches
            else:
                if len(matches) == 0:  # pragma: no cover
                    if die:
                        errormsg = f'No {which} matching "{label}" were found'
                        raise ValueError(errormsg)
                    else:
                        output = None
                else:
                    output = matches[
                        position]  # Return either the first or last match (usually), used by get_intervention()

            return output

    def get_interventions(self, label=None, partial=False, as_inds=False):
        """
        Find the matching intervention(s) by label, index, or type. If None, return
        all interventions. If the label provided is "summary", then print a summary
        of the interventions (index, label, type).

        Args:
            label (str, int, Intervention, list): the label, index, or type of intervention to get; if a list, iterate over one of those types
            partial (bool): if true, return partial matches (e.g. 'beta' will match all beta interventions)
            as_inds (bool): if true, return matching indices instead of the actual interventions
        """
        return self._get_ia('interventions', label=label, partial=partial, as_inds=as_inds, as_list=True)

    def get_intervention(self, label=None, partial=False, first=False, die=True):
        """
        Like get_interventions(), find the matching intervention(s) by label,
        index, or type. If more than one intervention matches, return the last
        by default. If no label is provided, return the last intervention in the list.

        Args:
            label (str, int, Intervention, list): the label, index, or type of intervention to get; if a list, iterate over one of those types
            partial (bool): if true, return partial matches (e.g. 'beta' will match all beta interventions)
            first (bool): if true, return first matching intervention (otherwise, return last)
            die (bool): whether to raise an exception if no intervention is found
        """
        return self._get_ia('interventions', label=label, partial=partial, first=first, die=die, as_inds=False,
                            as_list=False)

    def get_analyzers(self, label=None, partial=False, as_inds=False):
        """
        Same as get_interventions(), but for analyzers.
        """
        return self._get_ia('analyzers', label=label, partial=partial, as_list=True, as_inds=as_inds)

    def get_analyzer(self, label=None, partial=False, first=False, die=True):
        """
        Same as get_intervention(), but for analyzers.
        """
        return self._get_ia('analyzers', label=label, partial=partial, first=first, die=die, as_inds=False,
                            as_list=False)


# %% Define people classes

class State(sc.prettyobj):
    def __init__(self, name, dtype, fill_value=0, shape=None, label=None):
        """
        Args:
            name: name of the result as used in the model
            dtype: datatype
            fill_value: default value for this state upon model initialization
            shape: If not none, set to match a string in `pars` containing the dimensionality
            label: text used to construct labels for the result for displaying on plots and other outputs
        """
        self.name = name
        self.dtype = dtype
        self.fill_value = fill_value
        self.shape = shape
        self.label = label or name
        return

    @property
    def ndim(self):
        return len(sc.tolist(self.shape)) + 1

    def new(self, n):
        shape = sc.tolist(self.shape)
        shape.append(n)
        return np.full(shape, dtype=self.dtype, fill_value=self.fill_value)


class StochState(State):
    def __init__(self, name, dtype, distdict=None, **kwargs):
        super().__init__(name, dtype, kwargs)
        self.distdict = distdict
        return

    def new(self, n):
        shape = sc.tolist(self.shape)
        shape.append(n)
        return ssu.sample(**self.distdict, size=tuple(shape))


base_states = ssu.named_dict(
    State('uid', sss.default_int),
    State('age', sss.default_float),
    State('female', bool, False),
    State('debut', sss.default_float),
    State('dead', bool, False),
    State('ti_dead', sss.default_float, np.nan),  # Time index for death
    State('scale', sss.default_float, 1.0),
)


class BasePeople(sc.prettyobj):
    """
    A class to handle all the boilerplate for people -- note that as with the
    BaseSim vs Sim classes, everything interesting happens in the People class,
    whereas this class exists to handle the less interesting implementation details.
    """

    def __init__(self, n, states=None, *args, **kwargs):
        """ Initialize essential attributes """

        super().__init__(*args, **kwargs)
        self.initialized = False
        self.version = __version__  # Store version info

        # Initialize states, networks, modules
        self.states = sc.mergedicts(base_states, states)
        self.networks = ssu.named_dict()
        self._modules = sc.autolist()

        # Private variables relating to dynamic allocation
        self._data = dict()
        self._n = n  # Number of agents (initial)
        self._s = self._n  # Underlying array sizes
        self._inds = None  # No filtering indices

        # Initialize underlying storage and map arrays
        for state_name, state in self.states.items():
            self._data[state_name] = state.new(self._n)
        self._map_arrays()
        self['uid'][:] = np.arange(self._n)

        # Define lock attribute here, since BasePeople.lock()/unlock() requires it
        self._lock = False  # Prevent further modification of keys

        return

    def initialize(self, popdict=None):
        """ Initialize people by setting their attributes """
        if popdict is None:
            self['age'][:] = np.random.random(size=self.n) * 100
            self['female'][:] = np.random.choice([False, True], size=self.n)
        else:
            # Use random defaults
            self['age'][:] = popdict['age']
            self['female'][:] = popdict['female']
        self.initialized = True
        return

    def __len__(self):
        """ Length of people """
        try:
            arr = getattr(self, base_key)
            return len(arr)
        except Exception as E:
            print(f'Warning: could not get length of People (could not get self.{base_key}: {E})')
            return 0

    @property
    def n(self):
        return len(self)

    def _len_arrays(self):
        """ Length of underlying arrays """
        return len(self._data[base_key])

    def lock(self):
        """ Lock the people object to prevent keys from being added """
        self._lock = True
        return

    def unlock(self):
        """ Unlock the people object to allow keys to be added """
        self._lock = False
        return

    def _grow(self, n):
        """
        Increase the number of agents stored

        Automatically reallocate underlying arrays if required
        
        Args:
            n (int): Number of new agents to add
        """
        orig_n = self._n
        new_total = orig_n + n
        if new_total > self._s:
            n_new = max(n, int(self._s / 2))  # Minimum 50% growth
            for state_name, state in self.states.items():
                self._data[state_name] = np.concatenate([self._data[state_name], state.new(n_new)],
                                                        axis=self._data[state_name].ndim - 1)
            self._s += n_new
        self._n += n
        self._map_arrays()
        new_inds = np.arange(orig_n, self._n)
        return new_inds

    def _map_arrays(self, keys=None):
        """
        Set main simulation attributes to be views of the underlying data

        This method should be called whenever the number of agents required changes
        (regardless of whether the underlying arrays have been resized)
        """
        row_inds = slice(None, self._n)

        # Handle keys
        if keys is None: keys = self.states.keys()
        keys = sc.tolist(keys)

        # Map arrays for selected keys
        for k in keys:
            arr = self._data[k]
            if arr.ndim == 1:
                rsetattr(self, k, arr[row_inds])
            elif arr.ndim == 2:
                rsetattr(self, k, arr[:, row_inds])
            else:
                errormsg = 'Can only operate on 1D or 2D arrays'
                raise TypeError(errormsg)

        return

    def __getitem__(self, key):
        """ Allow people['attr'] instead of getattr(people, 'attr')
            If the key is an integer, alias `people.person()` to return a `Person` instance
        """
        if isinstance(key, int):
            return self.person(key)
        else:
            return self.__getattribute__(key)

    def __setitem__(self, key, value):
        """ Ditto """
        if self._lock and key not in self.__dict__:  # pragma: no cover
            errormsg = f'Key "{key}" is not an attribute of people and the people object is locked; see people.unlock()'
            raise AttributeError(errormsg)
        return self.__setattr__(key, value)

    def __iter__(self):
        """ Iterate over people """
        for i in range(len(self)):
            yield self[i]

    def _brief(self):
        """
        Return a one-line description of the people -- used internally and by repr();
        see people.brief() for the user version.
        """
        try:
            string = f'People(n={len(self):0n})'
        except Exception as E:  # pragma: no cover
            string = sc.objectid(self)
            string += f'Warning, sim appears to be malformed:\n{str(E)}'
        return string

    def set(self, key, value):
        """
        Set values. Note that this will raise an exception the shapes don't match,
        and will automatically cast the value to the existing type
        """
        self[key][:] = value[:]

    def get(self, key):
        """ Convenience method -- key can be string or list of strings """
        if isinstance(key, str):
            return self[key]
        elif isinstance(key, list):
            arr = np.zeros((len(self), len(key)))
            for k, ky in enumerate(key):
                arr[:, k] = self[ky]
            return arr

    @property
    def alive(self):
        """ Alive boolean """
        return ~self.dead

    @property
    def f_inds(self):
        """ Indices of everyone female """
        return self.true('female')

    @property
    def m_inds(self):
        """ Indices of everyone male """
        return self.false('female')

    @property
    def active(self):
        """ Indices of everyone sexually active  """
        return (self.age >= self.debut) & self.alive

    @property
    def int_age(self):
        """ Return ages as an integer """
        return np.array(self.age, dtype=sss.default_int)

    @property
    def round_age(self):
        """ Rounds age up to the next highest integer"""
        return np.array(np.ceil(self.age))

    @property
    def alive_inds(self):
        """ Indices of everyone alive """
        return self.true('alive')

    @property
    def n_alive(self):
        """ Number of people alive """
        return len(self.alive_inds)

    def true(self, key):
        """ Return indices matching the condition """
        return self[key].nonzero()[-1]

    def false(self, key):
        """ Return indices not matching the condition """
        return (~self[key]).nonzero()[-1]

    def defined(self, key):
        """ Return indices of people who are not-nan """
        return (~np.isnan(self[key])).nonzero()[0]

    def undefined(self, key):
        """ Return indices of people who are nan """
        return np.isnan(self[key]).nonzero()[0]

    def count(self, key, weighted=True):
        """ Count the number of people for a given key """
        inds = self[key].nonzero()[0]
        if weighted:
            out = self.scale[inds].sum()
        else:
            out = len(inds)
        return out

    def count_any(self, key, weighted=True):
        """ Count the number of people for a given key for a 2D array if any value matches """
        inds = self[key].sum(axis=0).nonzero()[0]
        if weighted:
            out = self.scale[inds].sum()
        else:
            out = len(inds)
        return out

    def keys(self):
        """ Returns keys for all non-derived properties of the people object """
        return [state.name for state in self.states]

    def indices(self):
        """ The indices of each people array """
        return np.arange(len(self))

    def to_arr(self):
        """ Return as numpy array """
        arr = np.empty((len(self), len(self.keys())), dtype=sss.default_float)
        for k, key in enumerate(self.keys()):
            if key == 'uid':
                arr[:, k] = np.arange(len(self))
            else:
                arr[:, k] = self[key]
        return arr

    def to_list(self):
        """ Return all people as a list """
        return list(self)


class FlexDict(dict):
    """
    A dict that allows more flexible element access: in addition to obj['a'],
    also allow obj[0]. Lightweight implementation of the Sciris odict class.
    """

    def __getitem__(self, key):
        """ Lightweight odict -- allow indexing by number, with low performance """
        try:
            return super().__getitem__(key)
        except KeyError as KE:
            try:  # Assume it's an integer
                dictkey = self.keys()[key]
                return self[dictkey]
            except:
                raise sc.KeyNotFoundError(KE)  # Raise the original error

    def keys(self):
        return list(super().keys())

    def values(self):
        return list(super().values())

    def items(self):
        return list(super().items())
