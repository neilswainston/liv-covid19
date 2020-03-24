'''
(c) University of Liverpool 2020

All rights reserved.

@author: neilswainston
'''
# pylint: disable=invalid-name
# pylint: disable=too-many-arguments
import os.path

from opentrons import simulate


metadata = {'apiLevel': '2.0',
            'author': 'Neil Swainston <neil.swainston@liverpool.ac.uk>',
            'description': 'simple'}

_TIP_RACK_TYPE = 'opentrons_96_filtertiprack_20ul'

_REAGENT_PLATE = {
    'type': 'nest_12_reservoir_15ml',
    'components': {'primer_mix': 'A1',
                   'rt_reaction_mix': 'A2',
                   'sequenase_mix_1': 'A3',
                   'sequenase_mix_2': 'A4'}
}

_SRC_PLATES = {
    'type': '4ti_96_wellplate_350ul'
}

_DST_PLATES = {
    'type': '4ti_96_wellplate_350ul'
}


def run(protocol):
    '''Run protocol.'''
    # Add temp deck:
    temp_mod = protocol.load_module('Temperature Module', 7)
    temp_mod.set_temperature(23)

    # Setup tip racks:
    reag_tip_rack, src_tip_rack = _add_tip_racks(protocol)

    # Add pipette:
    pipette = protocol.load_instrument(
        'p50_multi', 'left', tip_racks=[reag_tip_rack, src_tip_rack])

    # Setup plates:
    reag_plt, src_plt, dst_plt = _add_plates(protocol, temp_mod)

    # Add operations:
    _add_operations(protocol, temp_mod, pipette, src_tip_rack, reag_plt,
                    src_plt, dst_plt)


def _add_tip_racks(protocol):
    '''Add tip racks.'''
    # Add source and destination tip-rack:
    src_tip_rack = protocol.load_labware(_TIP_RACK_TYPE, 1)

    # Add reagent tip-rack:
    reag_tip_rack = protocol.load_labware(_TIP_RACK_TYPE, 10)

    return reag_tip_rack, src_tip_rack


def _add_plates(protocol, temp_deck):
    '''Add plates.'''
    # Add reagent plate:
    reag_plt = protocol.load_labware(_REAGENT_PLATE['type'], 11)

    # Add source and destination plates:
    src_plt = protocol.load_labware(_SRC_PLATES['type'], 4, 'src_plt')
    dst_plt = temp_deck.load_labware(_DST_PLATES['type'], 'dst_plt')

    return reag_plt, src_plt, dst_plt


def _add_operations(protocol, temp_mod, pipette, _, reag_plt, __, dst_plt):
    '''Add operations.'''

    # Transfer reagents:
    _, reag_well = _get_plate_well(reag_plt, 'rt_reaction_mix')

    for dst_col in dst_plt.columns():
        pipette.distribute(7.0, reag_plt[reag_well], dst_col)

    protocol.delay(minutes=10)
    temp_mod.set_temperature(53)
    protocol.delay(minutes=10)
    temp_mod.set_temperature(80)
    protocol.delay(minutes=10)


def _get_plate_well(reag_plt, reagent):
    '''Get reagent plate-well.'''
    well = _REAGENT_PLATE['components'].get(reagent, None)

    if well:
        return reag_plt, well

    return None


def main():
    '''main method.'''
    filename = os.path.realpath(__file__)

    with open(filename) as protocol_file:
        runlog, _ = simulate.simulate(protocol_file, filename)
        print(simulate.format_runlog(runlog))


if __name__ == '__main__':
    main()
