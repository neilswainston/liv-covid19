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

_SAMPLE_PLATE_TYPE = '4titude_96_wellplate_200ul'

_RNA_PLATE_WELLS = {'plate_1': ['A1', 'B1'], 'plate_2': ['C5', 'C6']}


def run(protocol):
    '''Run protocol.'''
    # Setup:
    p10_multi, src_plt, dst_plt = _setup(protocol)

    # Pick:
    _pick(protocol, p10_multi, src_plt, dst_plt)


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
        [protocol.load_labware('opentrons_96_filtertiprack_10ul', 5)]

    # Add pipette:
    p10_multi = protocol.load_instrument(
        'p10_multi', 'left', tip_racks=tip_racks_10)

    # Add plates:
    src_plt = protocol.load_labware(_SAMPLE_PLATE_TYPE, 6, 'sample')
    dst_plt = therm_mod.load_labware(_SAMPLE_PLATE_TYPE, 'RNA')

    return p10_multi, src_plt, dst_plt


def _pick(protocol, p10_multi, src_plt, dst_plt):
    '''Pick.'''
    # Add RNA samples:
    protocol.comment('\nPick RNA samples')
    tip_idx = -1
    dst_well_idx = 0

    for idx, (src_plt_name, src_wells) in enumerate(_RNA_PLATE_WELLS.items()):
        src_plt._display_name = src_plt._display_name.replace(src_plt.name,
                                                              src_plt_name)

        src_plt.name = src_plt_name

        for src_well in src_wells:
            p10_multi.pick_up_tip(p10_multi.tip_racks[0].wells()[tip_idx],
                                  presses=1, increment=0)

            p10_multi.aspirate(5.0, src_plt[src_well])
            p10_multi.dispense(5.0, dst_plt.wells()[dst_well_idx])
            p10_multi.drop_tip()
            tip_idx -= 1
            dst_well_idx += 1

        if idx < len(_RNA_PLATE_WELLS) - 1:
            protocol.pause('''
                Remove %s.
                Add %s to %s.
            ''' % (src_plt,
                   list(_RNA_PLATE_WELLS)[idx + 1], src_plt.parent))


def main():
    '''main method.'''
    filename = os.path.realpath(__file__)

    with open(filename) as protocol_file:
        runlog, _ = simulate.simulate(protocol_file, filename)
        print(simulate.format_runlog(runlog))


if __name__ == '__main__':
    main()
