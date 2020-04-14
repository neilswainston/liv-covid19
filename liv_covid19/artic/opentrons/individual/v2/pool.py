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
    'components': {'water': 'A8'}
}

_SAMPLE_PLATE = {
    'type': '4titude_96_wellplate_200ul',
    'last': ['H12', 'H12']
}


def run(protocol):
    '''Run protocol.'''
    # Setup:
    p300_multi, reag_plt, src_plts, dest_plt = _setup(protocol)

    # Add water:
    protocol.comment('\nAdd water')
    _distribute_reagent(p300_multi, reag_plt, dest_plt, [1], 'water', 45,
                        return_tip=True)

    # Combine Pool A and Pool B:
    protocol.comment('\nCombine Pool A and Pool B')
    _pool(p300_multi, src_plts, dest_plt)


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
    tip_racks_200 = \
        [protocol.load_labware('opentrons_96_filtertiprack_200ul', slot)
         for slot in [2]]

    # Add reagent plate:
    reag_plt = protocol.load_labware(_REAGENT_PLATE['type'], 5)

    # Add pipettes:
    p300_multi = protocol.load_instrument(
        'p300_multi', 'right', tip_racks=tip_racks_200)

    # Add source, thermo and mag plates:
    src_plts = [therm_mod.load_labware(_SAMPLE_PLATE['type'], 'PCR')]
    dest_plt = protocol.load_labware(_SAMPLE_PLATE['type'], 6, 'final_clean')

    if len(_SAMPLE_PLATE['last']) > 1:
        src_plts.append(temp_deck.load_labware(_SAMPLE_PLATE['type'], 'PCR2'))

    return p300_multi, reag_plt, src_plts, dest_plt


def _pool(p300_multi, src_plts, dst_plt):
    '''Pool A and B step.'''
    start_tip = [rack.next_tip() for rack in p300_multi.tip_racks][0]
    tip = start_tip

    for src_plt_idx, (src_plt, num_cols) in \
            enumerate(zip(src_plts, _get_num_cols())):
        for col_idx in range(int(num_cols // 2)):
            p300_multi.consolidate(
                2.5,
                [src_plt.columns()[idx] for idx in [col_idx, col_idx + 6]],
                dst_plt.columns()[col_idx + (src_plt_idx * 6)],
                mix_after=(3, 50.0),
                trash=False,
                disposal_volume=0)

            tip = tip.parent.rows_by_name()['A'][int(tip.display_name[1])]
            p300_multi.starting_tip = tip


def _distribute_reagent(pipette, reag_plt, dst_plt, dst_cols, reagent, vol,
                        return_tip=False, mix_before=None, air_gap=0,
                        top=None, bottom=None, blow_out=False):
    '''Distribute reagent.'''
    pipette.pick_up_tip()

    _, reag_well = _get_plate_well(reag_plt, reagent)

    dest_cols = []

    for dst_col in dst_cols:
        dest_cols.extend(
            dst_plt.rows_by_name()['A'][
                dst_col - 1:dst_col - 1 + sum(_get_num_cols()) // 2])

    pipette.distribute(vol,
                       reag_plt.wells_by_name()[reag_well],
                       [well.top(top) if top is not None
                        else (well.bottom(bottom) if bottom is not None
                              else well)
                        for well in dest_cols],
                       new_tip='never',
                       disposal_volume=0,
                       mix_before=mix_before,
                       air_gap=air_gap,
                       blow_out=blow_out)

    if return_tip:
        pipette.return_tip()
    else:
        pipette.drop_tip()


def _get_num_cols():
    '''Get number of sample columns.'''
    return [int(last[1:]) for last in _SAMPLE_PLATE['last']]


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
