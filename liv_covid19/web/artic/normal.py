'''
(c) University of Liverpool 2020

Licensed under the MIT License.

To view a copy of this license, visit <http://opensource.org/licenses/MIT/>..

@author: neilswainston
'''
# pylint: disable=invalid-name
# pylint: disable=wrong-import-order
import os.path

from liv_covid19.web.artic import utils
import numpy as np
import pandas as pd


def run(in_filename, out_dir, target_mass, temp_deck):
    '''run.'''
    in_df = _get_data(in_filename)

    # Check validity:
    min_val = target_mass / 7.5
    assert in_df.min().min() >= min_val, \
        'Invalid concentration(s) of < %.2ful/ng detected' % min_val

    # Convert to vol required for 50ng:
    in_df = target_mass / in_df

    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    # Write Mantis worklist:
    _get_mantis(in_df).to_csv(os.path.join(out_dir, 'mantis.csv'),
                              index=False, header=False)

    # Get tabular data:
    tab_df = _to_tabular(in_df)

    # Get Mosquito worklist:
    mosquito_df = _get_mosquito(tab_df)

    # Write Mosquito plate:
    mosquito_df.to_csv(os.path.join(out_dir, 'mosquito.csv'),
                       index=False)

    # Write Opentrons worklist:
    _get_ot(tab_df, temp_deck, out_dir)


def _get_data(in_filename):
    '''Get data.'''
    in_df = pd.read_csv(in_filename, header=None)
    in_df.dropna(axis=0, how='any', inplace=True)
    in_df.dropna(axis=1, how='any', inplace=True)
    in_df.index = [val + 1 for val in range(len(in_df))]
    in_df.columns = [val + 1 for val in range(len(in_df.columns))]
    return in_df


def _to_tabular(in_df):
    '''Convert to tabular data.'''
    n, k = in_df.shape

    data = {'conc': in_df.to_numpy().ravel('F'),
            'Column': np.asarray(in_df.columns).repeat(n),
            'Row': np.tile(np.asarray(in_df.index), k)}

    return pd.DataFrame(data, columns=['Column', 'Row', 'conc'])


def _get_mantis(in_df):
    '''Get Mantis worklist.'''
    return 12.5 - in_df


def _get_mosquito(tab_df, max_vol=12000):
    '''Get Mosquito worklist.'''
    df = tab_df.copy()

    # Add missing plate positions and destinations:
    df['Position'] = 2
    df['Column dest'] = df['Column']
    df['Row dest'] = df['Row']
    df['Position dest'] = 3

    # Convert to nl:
    df['conc'] = df['conc'] * 1000

    # Check against maximum volume:
    over_max_df = df[df['conc'] > max_vol].copy()

    while not over_max_df.empty:
        df.loc[df['conc'] > max_vol, 'conc'] = \
            df.loc[df['conc'] > max_vol, 'conc'] / 2

        over_max_df.loc[:, 'conc'] = over_max_df.loc[:, 'conc'] / 2
        df = df.append(over_max_df).sort_index()

        over_max_df = df[df['conc'] > max_vol]

    # Reorder and rename columns:
    df = df[['Position', 'Column', 'Row',
             'Position dest', 'Column dest', 'Row dest',
             'conc']]

    df.columns = ['Position', 'Column', 'Row',
                  'Position', 'Column', 'Row',
                  'Nanolitres']

    return df


def _get_ot(df, temp_deck, out_dir):
    '''Get OpenTrons worklists.'''
    resp = df.apply(_to_tuple, axis=1)
    dna_concs = dict(resp.tolist())

    # Convert:
    py_dir = 'liv_covid19/artic/opentrons/'

    for filename in ['normalisation.py']:
        utils.replace(os.path.join(py_dir, filename), out_dir,
                      temp_deck=temp_deck,
                      dna_concs=dna_concs)


def _to_tuple(row):
    '''Convert row to tuple.'''
    well = chr(int(row['Row']) - 1 + ord('A')) + str(int(row['Column']))
    return (well, row['conc'])
