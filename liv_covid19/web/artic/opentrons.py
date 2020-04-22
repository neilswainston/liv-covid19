'''
(c) University of Liverpool 2020

Licensed under the MIT License.

To view a copy of this license, visit <http://opensource.org/licenses/MIT/>..

@author: neilswainston
'''
# pylint: disable=invalid-name
import datetime
import os.path
import sys
import uuid

import pandas as pd


def run(in_filename, out_dir):
    '''run.'''
    df = pd.read_csv(in_filename, dtype={'id': object, 'plate_id': object})

    # Generate unique destination plate id:
    dst_plt_id = '%s-%s' % (datetime.datetime.now().strftime('%Y%m%d'),
                            str(uuid.uuid4())[:8])

    # Select valid wells (those that are non-negative):
    dst_wells = _get_wells(df[df['status'] != 'NEG'])

    # Update the DataFrame:
    df.loc[df['status'] != 'NEG', 'dest_plate_id'] = dst_plt_id
    df.loc[df['status'] != 'NEG', 'dest_well'] = dst_wells

    # Create 'out' directory if it does not exist:
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    # Write updated DataFrame:
    df.to_csv(os.path.join(out_dir, '%s.csv' % dst_plt_id), index=False)

    # Get OpenTrons worklist Python scripts:
    last_well = dst_wells[-1]

    rna_plate_wells = {
        key: grp_df['well'].to_list()
        for key, grp_df in df[df['status'] != 'NEG'].groupby('plate_id')}

    for filename in [
        'liv_covid19/artic/opentrons/individual/picker.py',
        'liv_covid19/artic/opentrons/composite/v2/pre_pcr.py',
        'liv_covid19/artic/opentrons/individual/v2/pool.py',
            'liv_covid19/artic/opentrons/individual/barcode_multi.py']:
        _replace(filename, out_dir, rna_plate_wells, last_well)


def _get_wells(df):
    '''Get wells.'''
    return [get_well_pos(idx) for idx in range(len(df))]


def get_well_pos(idx, shape=(8, 12)):
    '''Get well position from index.'''
    assert idx < shape[0] * shape[1]

    row = chr((idx % shape[0]) + ord('A'))
    col = idx // shape[0] + 1

    return row + str(col)


def _replace(flnme_in, out_dir, rna_plate_wells, last_well):
    '''Replace.'''
    flnme_out = os.path.join(out_dir, os.path.basename(flnme_in))

    with open(flnme_in, 'rt') as file_in, open(flnme_out, 'wt') as file_out:
        for line in file_in:
            line = '_SAMPLE_PLATE_LAST = \'%s\'' % last_well \
                if line.startswith('_SAMPLE_PLATE_LAST') else line

            line = '_RNA_PLATE_WELLS = %s' % rna_plate_wells \
                if line.startswith('_RNA_PLATE_WELLS') else line

            file_out.write(line)


def main(args):
    '''main method.'''
    run(args[0], args[1])


if __name__ == '__main__':
    main(sys.argv[1:])
