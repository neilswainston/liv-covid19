'''
(c) University of Liverpool 2020

Licensed under the MIT License.

To view a copy of this license, visit <http://opensource.org/licenses/MIT/>..

@author: neilswainston
'''
# pylint: disable=invalid-name
import os.path
import sys

import numpy as np
import pandas as pd


def run(in_filename, out_dir):
    '''run.'''
    in_df = _get_data(in_filename)

    # Convert to vol required for 50ng:
    in_df = 50 / in_df

    # Check validity:
    assert in_df.max().max() <= 12.5

    mantis_df = 12.5 - in_df

    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    # Write Mantis worklist:
    mantis_df.to_csv(os.path.join(out_dir, 'mantis.csv'),
                     index=False, header=False)

    # Get Mosquito worklist:
    mosquito_df = _get_mosquito(in_df)

    # Write Mantis plate:
    mosquito_df.to_csv(os.path.join(out_dir, 'mosquito.csv'),
                       index=False)


def _get_data(in_filename):
    '''Get data.'''
    in_df = pd.read_csv(in_filename, header=None)
    in_df.dropna(axis=0, how='any', inplace=True)
    in_df.dropna(axis=1, how='any', inplace=True)
    in_df.index = [val + 1 for val in range(len(in_df))]
    in_df.columns = [val + 1 for val in range(len(in_df.columns))]
    return in_df


def _get_mosquito(in_df, max_vol=12000):
    '''Get Mosquito worklist.'''

    # Convert to tabular data:
    n, k = in_df.shape

    data = {'Nanolitres': in_df.to_numpy().ravel('F') * 1000,
            'Column': np.asarray(in_df.columns).repeat(n),
            'Row': np.tile(np.asarray(in_df.index), k)}

    df = pd.DataFrame(data, columns=['Column', 'Row', 'Nanolitres'])

    # Add missing plate positions and destinations:
    df['Position'] = 2
    df['Column dest'] = df['Column']
    df['Row dest'] = df['Row']
    df['Position dest'] = 3

    # Check against maximum volume:
    over_max_df = df[df['Nanolitres'] > max_vol].copy()

    while not over_max_df.empty:
        df.loc[df['Nanolitres'] > max_vol, 'Nanolitres'] = \
            df.loc[df['Nanolitres'] > max_vol, 'Nanolitres'] / 2

        over_max_df.loc[:, 'Nanolitres'] = over_max_df.loc[:, 'Nanolitres'] / 2
        df = df.append(over_max_df).sort_index()

        over_max_df = df[df['Nanolitres'] > max_vol]

    # Reorder and rename columns:
    df = df[['Position', 'Column', 'Row',
             'Position dest', 'Column dest', 'Row dest',
             'Nanolitres']]

    df.columns = ['Position', 'Column', 'Row',
                  'Position', 'Column', 'Row',
                  'Nanolitres']

    return df


def main(args):
    '''main method.'''
    run(args[0], args[1])


if __name__ == '__main__':
    main(sys.argv[1:])
