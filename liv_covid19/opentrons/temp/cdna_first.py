'''
(c) University of Liverpool 2020

All rights reserved.

@author: neilswainston
'''
# pylint: disable=invalid-name
# pylint: disable=too-many-arguments
import os.path

from opentrons import simulate


metadata = {'apiLevel': '2.1',
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
    temp_mod = protocol.load_module('Temperature Module', 9)
    temp_mod.set_temperature(65)

    # Setup tip racks:
    src_tip_rack = protocol.load_labware(_TIP_RACK_TYPE, 3)

    reag_tip_racks = [protocol.load_labware(_TIP_RACK_TYPE, slot)
                      for slot in [10, 11]]

    # Add pipette:
    pipette = protocol.load_instrument(
        'p50_multi', 'left', tip_racks=reag_tip_racks + [src_tip_rack])

    # Setup plates:
    reag_plt, src_plt, dst_plt = _add_plates(protocol, temp_mod)

    # Add primer mix:
    protocol.comment('\nAdd primer mix')
    _add_primer_mix(pipette, reag_plt, dst_plt)

    # Add RNA samples:
    protocol.comment('\nAdd RNA samples')
    pipette.starting_tip = src_tip_rack['A1']
    _add_rna_samples(pipette, src_plt, dst_plt)

    # Incubate at 65C for 5 minute:
    _incubate(protocol, temp_mod, 65, 5)

    # Incubate (on ice) / at min temp for 1 minute:
    _incubate(protocol, temp_mod, 4, 1)

    # Add RT reaction mix:
    protocol.comment('\nAdd RT reaction mix')
    pipette.starting_tip = reag_tip_racks[0]['A2']
    _add_reagent(pipette, reag_plt, dst_plt, 'rt_reaction_mix', 7.0)

    # Incubate at 23C for 10 minute:
    _incubate(protocol, temp_mod, 23, 10)

    # Incubate at 53C for 10 minute:
    _incubate(protocol, temp_mod, 53, 10)

    # Incubate at 80C for 10 minute:
    _incubate(protocol, temp_mod, 80, 10)

    # Add sequenase mix 1:
    protocol.comment('\nAdd sequenase mix 1')
    _add_reagent(pipette, reag_plt, dst_plt, 'sequenase_mix_1', 4.9)

    # Incubate at 37C for 8 minute:
    _incubate(protocol, temp_mod, 37, 8)

    # Add sequenase mix 2:
    protocol.comment('\nAdd sequenase mix 2')
    _add_reagent(pipette, reag_plt, dst_plt, 'sequenase_mix_2', 0.6)

    # Incubate at 37C for 8 minute:
    _incubate(protocol, temp_mod, 37, 8)


def _add_plates(protocol, temp_deck):
    '''Add plates.'''
    # Add reagent plate:
    reag_plt = protocol.load_labware(_REAGENT_PLATE['type'], 8)

    # Add source and destination plates:
    src_plt = protocol.load_labware(_SRC_PLATES['type'], 6, 'src_plt')
    dst_plt = temp_deck.load_labware(_DST_PLATES['type'], 'dst_plt')

    return reag_plt, src_plt, dst_plt


def _incubate(protocol, temp_mod, temp, minutes, seconds=0):
    '''Incubate.'''
    temp_mod.set_temperature(temp)
    protocol.delay(minutes=minutes, seconds=seconds)


def _add_primer_mix(pipette, reag_plt, dst_plt):
    '''Add primer mix.'''
    pipette.pick_up_tip()

    _, reag_well = _get_plate_well(reag_plt, 'primer_mix')

    for dst_col in dst_plt.columns()[:1]:
        pipette.distribute(8.0, reag_plt[reag_well], dst_col,
                           new_tip='never', touch_tip=True)

    pipette.drop_tip()


def _add_rna_samples(pipette, src_plt, dst_plt):
    '''Add RNA samples.'''
    for src_col, dst_col in zip(src_plt.columns()[:1], dst_plt.columns()[:1]):
        pipette.transfer(5.0, src_col, dst_col, touch_tip=True)


def _add_reagent(pipette, reag_plt, dst_plt, reagent, vol):
    '''Add reagent.'''

    # Transfer reagents:
    _, reag_well = _get_plate_well(reag_plt, reagent)

    for dst_col in dst_plt.columns()[:1]:
        pipette.distribute(vol, reag_plt[reag_well], dst_col)


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
