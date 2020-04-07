'''
(c) University of Liverpool 2020

Licensed under the MIT License.

To view a copy of this license, visit <http://opensource.org/licenses/MIT/>..

@author: neilswainston
'''
# pylint: disable=invalid-name
# pylint: disable=protected-access
# pylint: disable=too-many-arguments
# pylint: disable=too-many-locals
import os.path

from opentrons import simulate


metadata = {'apiLevel': '2.1',
            'author': 'Neil Swainston <neil.swainston@liverpool.ac.uk>',
            'description': 'simple'}

_REAGENT_PLATE = {
    'type': 'nest_12_reservoir_15ml',
    'components': {'water': 'A8',
                   'endprep_mastermix': 'A9'}
}

_SAMPLE_PLATE = {
    'type': '4titude_96_wellplate_200ul',
}

_DNA_VOLS = {
    'A1': 3,
    'H12': 1
}


def run(protocol):
    '''Run protocol.'''
    # Setup:
    therm_mod, p10_single, p10_multi, reag_plt, src_plt, dst_plt = \
        _setup(protocol)

    # Normalise DNA concentrations:
    _normalise(protocol, therm_mod, p10_single, p10_multi, reag_plt, src_plt,
               dst_plt)


def _setup(protocol):
    '''Setup.'''
    # Add temp deck:
    therm_mod = protocol.load_module('thermocycler', 7)
    therm_mod.open_lid()
    therm_mod.set_block_temperature(4)
    therm_mod.set_lid_temperature(105)

    temp_deck = protocol.load_module('tempdeck', 4)
    temp_deck.set_temperature(4)

    # Setup tip racks:
    tip_racks_10 = \
        [protocol.load_labware('opentrons_96_filtertiprack_10ul', slot)
         for slot in [2, 3]]

    # Add pipettes:
    p10_single = protocol.load_instrument(
        'p10_single', 'left', tip_racks=tip_racks_10)

    # Add pipette:
    p10_multi = protocol.load_instrument(
        'p10_multi', 'right', tip_racks=tip_racks_10)

    # Add reagent plate:
    reag_plt = protocol.load_labware(_REAGENT_PLATE['type'], 5)

    # Add source, thermo and mag plates:
    src_plt = temp_deck.load_labware(_SAMPLE_PLATE['type'], 'src_plt')
    therm_plt = therm_mod.load_labware(_SAMPLE_PLATE['type'], 'dst_plt')

    return therm_mod, p10_single, p10_multi, reag_plt, src_plt, therm_plt


def _normalise(protocol, therm_mod, p10_single, p10_multi, reag_plt, src_plt,
               dst_plt):
    '''Generate cDNA.'''
    protocol.comment('\nNormalise DNA concentrations')

    # Add endprep mastermix:
    _distribute_reagent(p10_multi, reag_plt, dst_plt, [1],
                        'endprep_mastermix', 7.5,
                        return_tip=True)

    # Add water and DNA:
    _, reag_well = _get_plate_well(reag_plt, 'water')

    protocol.comment('\nAdd water and DNA')

    for well, vol in _DNA_VOLS.items():
        p10_single.consolidate([7.5 - vol, vol],
                               [reag_plt[reag_well], src_plt[well]],
                               dst_plt[well])

    # Incubate at 20C for 5 minute:
    therm_mod.close_lid()
    _incubate(therm_mod, 20, 5, lid_temp=105)

    # Incubate at 65C for 5 minute:
    _incubate(therm_mod, 65, 5, lid_temp=105)
    therm_mod.open_lid()


def _incubate(therm_mod, block_temp, minutes, seconds=0, lid_temp=None):
    '''Incubate.'''
    if lid_temp and therm_mod.lid_temperature != lid_temp:
        therm_mod.set_lid_temperature(lid_temp)

    therm_mod.set_block_temperature(block_temp,
                                    hold_time_minutes=minutes,
                                    hold_time_seconds=seconds)


def _distribute_reagent(pipette, reag_plt, dst_plt, dst_cols, reagent, vol,
                        return_tip=False, mix_before=None, air_gap=0,
                        top=None, bottom=None):
    '''Distribute reagent.'''
    pipette.pick_up_tip()

    _, reag_well = _get_plate_well(reag_plt, reagent)

    dest_cols = []

    for dst_col in dst_cols:
        dest_cols.extend(
            dst_plt.rows_by_name()['A'][
                dst_col - 1:dst_col - 1 + _get_num_cols()])

    pipette.distribute(vol,
                       reag_plt.wells_by_name()[reag_well],
                       [well.top(top) if top is not None
                        else (well.bottom(bottom) if bottom is not None
                              else well)
                        for well in dest_cols],
                       new_tip='never',
                       disposal_volume=0,
                       mix_before=mix_before,
                       air_gap=air_gap)

    if return_tip:
        pipette.return_tip()
    else:
        pipette.drop_tip()


def _get_num_cols():
    '''Get number of sample columns.'''
    return int(list(_DNA_VOLS.keys())[-1][1:])


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
