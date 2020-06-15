'''
(c) University of Liverpool 2020

Licensed under the MIT License.

To view a copy of this license, visit <http://opensource.org/licenses/MIT/>..

@author: neilswainston
'''
# pylint: disable=too-many-arguments
import os.path


def replace(flnme_in, out_dir,
            rna_plate_wells=None,
            last_well='H12',
            temp_deck='tempdeck',
            vol_scale=1.0,
            dna_concs=None):
    '''Replace.'''
    if not rna_plate_wells:
        rna_plate_wells = {'plate_1': []}

    if not dna_concs:
        dna_concs = {}

    flnme_out = os.path.join(out_dir, os.path.basename(flnme_in))

    with open(flnme_in, 'rt') as file_in, open(flnme_out, 'wt') as file_out:
        for line in file_in:
            line = '_SAMPLE_PLATE_LAST = \'%s\'' % last_well \
                if line.startswith('_SAMPLE_PLATE_LAST') else line

            line = '_RNA_PLATE_WELLS = %s' % rna_plate_wells \
                if line.startswith('_RNA_PLATE_WELLS') else line

            line = '_TEMP_DECK = \'%s\'' % temp_deck \
                if line.startswith('_TEMP_DECK') else line

            line = '_VOL_SCALE = %f' % vol_scale \
                if line.startswith('_VOL_SCALE') else line

            line = '_DNA_VOLS = %s' % dna_concs \
                if line.startswith('_DNA_VOLS') else line

            file_out.write(line)
