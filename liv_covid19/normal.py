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
    in_df = pd.read_csv(in_filename, header=None)
    in_df.dropna(axis=0, how='any', inplace=True)
    in_df.dropna(axis=1, how='any', inplace=True)
    in_df.index = [val + 1 for val in range(len(in_df))]
    in_df.columns = [val + 1 for val in range(len(in_df.columns))]

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


def _get_mosquito(in_df):
    '''Get Mosquito worklist.'''
    n, k = in_df.shape

    data = {'Nanolitres': in_df.to_numpy().ravel('F'),
            'Column': np.asarray(in_df.columns).repeat(n),
            'Row': np.tile(np.asarray(in_df.index), k)}

    mosquito_df = pd.DataFrame(data, columns=['Column', 'Row', 'Nanolitres'])
    mosquito_df['Position'] = 2
    mosquito_df['Column dest'] = mosquito_df['Column']
    mosquito_df['Row dest'] = mosquito_df['Row']
    mosquito_df['Position dest'] = 3

    mosquito_df = mosquito_df[['Position', 'Column', 'Row',
                               'Position dest', 'Column dest', 'Row dest',
                               'Nanolitres']]

    mosquito_df.columns = ['Position', 'Column', 'Row',
                           'Position', 'Column', 'Row',
                           'Nanolitres']

    return mosquito_df


def main(args):
    '''main method.'''
    run(args[0], args[1])


if __name__ == '__main__':
    main(sys.argv[1:])
