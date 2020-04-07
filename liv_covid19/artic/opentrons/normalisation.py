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
    'components': {'barcodes_1': 'A1',
                   'barcodes_2': 'A2',
                   'barcodes_3': 'A3',
                   'ligation_mastermix': 'A4',
                   'beads': 'A5',
                   'ethanol_1': 'A6',
                   'ethanol_2': 'A7',
                   'water': 'A8',
                   'waste_1': 'A11',
                   'waste_2': 'A12'}
}

_SAMPLE_PLATE = {
    'type': '4titude_96_wellplate_200ul',
}

_DNA_VOLS = {
    'A1': 10,
    'H12': 1
}


def run(protocol):
    '''Run protocol.'''
    # Setup:
    therm_mod, p10_single, reag_plt, src_plt, dst_plt = _setup(protocol)

    # Normalise DNA concentrations:
    _normalise(protocol, therm_mod, p10_single, reag_plt, src_plt, dst_plt)


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

    # Add reagent plate:
    reag_plt = protocol.load_labware(_REAGENT_PLATE['type'], 5)

    # Add source, thermo and mag plates:
    src_plt = temp_deck.load_labware(_SAMPLE_PLATE['type'], 'src_plt')
    therm_plt = therm_mod.load_labware(_SAMPLE_PLATE['type'], 'dst_plt')

    return therm_mod, p10_single, reag_plt, src_plt, therm_plt


def _normalise(protocol, therm_mod, p10_single, reag_plt, src_plt, dst_plt):
    '''Generate cDNA.'''
    protocol.comment('\nNormalise DNA concentrations')

    # Add water:
    _, reag_well = _get_plate_well(reag_plt, 'water')

    protocol.comment('\nAdd water')

    p10_single.distribute(
        [12.5 - vol for vol in _DNA_VOLS.values()],
        reag_plt[reag_well],
        [dst_plt.wells_by_name()[well_name] for well_name in _DNA_VOLS],
        disposal_volume=0)

    # Add DNA:
    protocol.comment('\nAdd DNA')

    p10_single.transfer(
        list(_DNA_VOLS.values()),
        [src_plt.wells_by_name()[well_name] for well_name in _DNA_VOLS],
        [dst_plt.wells_by_name()[well_name] for well_name in _DNA_VOLS],
        disposal_volume=0)

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
