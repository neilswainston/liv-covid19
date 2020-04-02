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
    'components': {'primer_mix': 'A1',
                   'rt_reaction_mix': 'A2',
                   'primer_pool_a_mastermix': 'A3',
                   'primer_pool_b_mastermix': 'A4',
                   'beads': 'A5',
                   'ethanol': 'A6',
                   'water': 'A7',
                   'waste': 'A12'}
}

_SAMPLE_PLATE = {
    'type': '4titude_96_wellplate_200ul',
    'last': ['H6']
}

_MAG_PLATE = {
    'type': '4ti_96_wellplate_350ul'
}


def run(protocol):
    '''Run protocol.'''
    # Setup:
    mag_decks, p300_multi, reag_plt, therm_plts, mag_plts = _setup(protocol)

    # Cleanup:
    _cleanup(protocol, mag_decks, p300_multi, reag_plt, therm_plts, mag_plts)


def _setup(protocol):
    '''Setup.'''
    # Add temp deck:
    therm_mod = protocol.load_module('thermocycler', 7)
    therm_mod.open_lid()
    therm_mod.set_block_temperature(4)
    therm_mod.set_lid_temperature(105)

    temp_deck = protocol.load_module('tempdeck', 4)
    temp_deck.set_temperature(4)

    mag_decks = [protocol.load_module('magdeck', 1)
                 for _ in _SAMPLE_PLATE['last']]

    # Setup tip racks:
    tip_racks_200 = \
        [protocol.load_labware('opentrons_96_filtertiprack_200ul', slot)
         for slot in [6, 9]]

    # Add pipette:
    p300_multi = protocol.load_instrument(
        'p300_multi', 'right', tip_racks=tip_racks_200)

    # Add reagent plate:
    reag_plt = protocol.load_labware(_REAGENT_PLATE['type'], 5)

    # Thermo and mag plates:
    therm_plts = [therm_mod.load_labware(_SAMPLE_PLATE['type'], 'dst_plt')]
    mag_plts = [mag_deck.load_labware(_MAG_PLATE['type'], 'dst_plt')
                for mag_deck in mag_decks]

    return mag_decks, p300_multi, reag_plt, therm_plts, mag_plts


def _cleanup(protocol, mag_decks, p300_multi, reag_plt, src_plts, dst_plts):
    '''Clean-up.'''
    protocol.comment('\nClean-up')

    # Add beads:
    protocol.comment('\nAdd beads')
    _distribute_reagent(p300_multi, reag_plt, dst_plts, [1], 'beads', 50,
                        return_tip=True, mix_before=(3, 200))

    # Combine Pool A and Pool B:
    protocol.comment('\nCombine Pool A and Pool B')
    dirty_tip = _cleanup_pool(p300_multi, src_plts, dst_plts)

    # Incubate 10 minutes:
    protocol.delay(minutes=10)

    # Engage MagDeck:
    for mag_deck, mag_plt in zip(mag_decks, dst_plts):
        engage_height = mag_plt._dimensions['zDimension']
        mag_deck.engage(height=engage_height)

    protocol.delay(minutes=5)

    # Slow flow rates:
    _set_flow_rate(protocol, p300_multi, aspirate=25, dispense=150)

    # Remove supernatant from magnetic beads:
    protocol.comment('\nRemove supernatant')
    _to_waste(p300_multi, dst_plts, reag_plt, 75, dirty_tip)

    # Wash twice with ethanol:
    air_gap = p300_multi.max_volume * 0.1

    for count in range(2):
        protocol.comment('\nEthanol #%i' % (count + 1))

        # TODO: vol + air_gap > p300_multi.max_volume,
        # therefore air_gap cannot be set.
        _distribute_reagent(p300_multi, reag_plt, dst_plts, [1], 'ethanol',
                            200, return_tip=count == 0, air_gap=0, top=0)

        protocol.delay(seconds=17)

        protocol.comment('\nEthanol waste #%i' % (count + 1))
        _to_waste(p300_multi, dst_plts, reag_plt, 250, dirty_tip,
                  air_gap=air_gap)

    # Dry:
    protocol.delay(seconds=30)

    # Disengage MagDeck:
    for mag_deck in mag_decks:
        mag_deck.disengage()

    # Resuspend in water:
    protocol.comment('\nResuspend in water')
    _transfer_reagent(p300_multi, reag_plt, dst_plts, 1, 'water', 15)

    # Incubate:
    protocol.delay(minutes=2)

    # Elute:
    mag_deck.engage(height=engage_height)
    protocol.delay(minutes=3)  # "Until eluate is clear and colourless"

    # Transfer clean product to a new well (move from col 1 to col 7, etc.):
    protocol.comment('\nTransfer clean product')
    _transfer_samples(p300_multi, dst_plts, dst_plts, 1, 7, 15)

    # Disengage MagDeck:
    mag_deck.disengage()


def _cleanup_pool(p300_multi, src_plts, dst_plts):
    '''Cleanup pool A and B step.'''
    start_tip = [rack.next_tip() for rack in p300_multi.tip_racks][0]
    tip = start_tip

    for idx, (src_plt, dst_plt) in enumerate(zip(src_plts, dst_plts)):
        for col_idx in range(_get_num_cols()[idx]):
            p300_multi.consolidate(
                25,
                [src_plt.columns()[idx] for idx in [col_idx, col_idx + 6]],
                dst_plt.columns()[col_idx],
                mix_after=(3, 25.0),
                trash=False,
                disposal_volume=0)

            tip = tip.parent.rows_by_name()['A'][int(tip.display_name[1])]
            p300_multi.starting_tip = tip

    return start_tip


def _to_waste(p300_multi, src_plts, waste_plt, vol, start_tip, air_gap=0):
    '''Move to waste.'''
    _, waste = _get_plate_well(waste_plt, 'waste')

    tip = start_tip
    p300_multi.starting_tip = tip

    for plt_idx, src_plt in enumerate(src_plts):
        for col_idx in range(_get_num_cols()[plt_idx]):
            p300_multi.transfer(
                vol,
                src_plt.columns()[col_idx],
                waste_plt[waste].top(),
                trash=False,
                disposal_volume=0,
                air_gap=air_gap)

            tip = tip.parent.rows_by_name()['A'][int(tip.display_name[1])]
            p300_multi.starting_tip = tip


def _transfer_samples(pipette, src_plts, dst_plts, src_col, dst_col, vol):
    '''Transfer samples.'''
    num_cols = _get_num_cols()

    for idx, (src_plt, dst_plt) in enumerate(zip(src_plts, dst_plts)):
        for src, dst in zip(
                src_plt.columns()[src_col - 1:src_col - 1 + num_cols[idx]],
                dst_plt.columns()[dst_col - 1:dst_col - 1 + num_cols[idx]]):
            pipette.transfer(vol, src, dst, mix_after=(3, vol),
                             disposal_volume=0)


def _distribute_reagent(pipette, reag_plt, dst_plts, dst_cols, reagent, vol,
                        return_tip=False, mix_before=None, air_gap=0,
                        top=None, bottom=None):
    '''Distribute reagent.'''
    pipette.pick_up_tip()

    _, reag_well = _get_plate_well(reag_plt, reagent)

    dest_cols = []

    for idx, dst_plt in enumerate(dst_plts):
        for dst_col in dst_cols:
            dest_cols.extend(
                dst_plt.rows_by_name()['A'][
                    dst_col - 1:dst_col - 1 + _get_num_cols()[idx]])

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


def _transfer_reagent(pipette, reag_plt, dst_plts, dst_col, reagent, vol):
    '''Transfer reagent.'''
    _, reag_well = _get_plate_well(reag_plt, reagent)

    for idx, dst_plt in enumerate(dst_plts):
        num_cols = _get_num_cols()[idx]

        for dst in dst_plt.columns()[dst_col - 1:dst_col - 1 + num_cols]:
            pipette.transfer(vol,
                             reag_plt[reag_well],
                             dst,
                             mix_after=(3, vol),
                             disposal_volume=0)


def _set_flow_rate(protocol, pipette, aspirate=None, dispense=None,
                   blow_out=None):
    '''Set flow rates.'''
    old_aspirate = pipette.flow_rate.aspirate
    old_dispense = pipette.flow_rate.dispense
    old_blow_out = pipette.flow_rate.blow_out

    if aspirate and aspirate != old_aspirate:
        protocol.comment('Updating aspirate from %i to %i'
                         % (old_aspirate, aspirate))
        pipette.flow_rate.aspirate = aspirate

    if dispense and dispense != old_dispense:
        protocol.comment('Updating dispense from %i to %i'
                         % (old_dispense, dispense))
        pipette.flow_rate.dispense = dispense

    if blow_out and blow_out != old_blow_out:
        protocol.comment('Updating blow_out from %i to %i'
                         % (old_blow_out, blow_out))
        pipette.flow_rate.blow_out = blow_out

    return old_aspirate, old_dispense, old_blow_out


def _get_num_cols():
    '''Get number of sample columns.'''
    return [int(well[1]) for well in _SAMPLE_PLATE['last']]


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
