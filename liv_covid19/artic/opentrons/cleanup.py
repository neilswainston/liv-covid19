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
    'components': {'beads': 'A5',
                   'ethanol_1': 'A6',
                   'ethanol_2': 'A7',
                   'water': 'A8',
                   'waste_1': 'A11',
                   'waste_2': 'A12'}
}

_SAMPLE_PLATE = {
    'type': '4titude_96_wellplate_200ul',
    'last': 'H12'
}

_MAG_PLATE = {
    'type': '4titude_96_wellplate_200ul'
}


def run(protocol):
    '''Run protocol.'''
    # Setup:
    mag_deck, p300_multi, reag_plt, src_plt, mag_plt = _setup(protocol)

    # Cleanup:
    _cleanup(protocol, mag_deck, p300_multi, reag_plt, src_plt, mag_plt,
             engage_height=mag_plt._dimensions['zDimension'])


def _setup(protocol):
    '''Setup.'''
    # Add temp deck:
    temp_deck = protocol.load_module('tempdeck', 4)
    temp_deck.set_temperature(4)

    mag_deck = protocol.load_module('magdeck', 1)

    # Setup tip racks:
    tip_racks_200 = \
        [protocol.load_labware('opentrons_96_filtertiprack_200ul', slot)
         for slot in [2, 3]]

    # Add pipettes:
    p300_multi = protocol.load_instrument(
        'p300_multi', 'right', tip_racks=tip_racks_200)

    # Add reagent plate:
    reag_plt = protocol.load_labware(_REAGENT_PLATE['type'], 5)

    # Add source, thermo and mag plates:
    src_plt = temp_deck.load_labware(_SAMPLE_PLATE['type'], 'src_plt')
    mag_plt = mag_deck.load_labware(_MAG_PLATE['type'], 'dst_plt')

    return mag_deck, p300_multi, reag_plt, src_plt, mag_plt


def _cleanup(protocol, mag_deck, p300_multi, reag_plt, src_plt, dst_plt,
             engage_height):
    '''Clean-up.'''
    protocol.comment('\nClean-up')

    # Add beads:
    protocol.comment('\nAdd beads')
    _distribute_reagent(p300_multi, reag_plt, dst_plt, [1], 'beads', 50,
                        return_tip=True)

    # Combine Pool A and Pool B:
    protocol.comment('\nCombine Pool A and Pool B')
    dirty_tip = _cleanup_pool(p300_multi, src_plt, dst_plt)

    # Incubate 10 minutes:
    protocol.delay(minutes=10)

    # Engage MagDeck:
    mag_deck.engage(height=engage_height)
    protocol.delay(minutes=5)

    # Slow flow rates:
    _set_flow_rate(protocol, p300_multi, aspirate=25, dispense=150)

    # Remove supernatant from magnetic beads:
    protocol.comment('\nRemove supernatant')
    _to_waste(p300_multi, dst_plt, reag_plt, 75, dirty_tip, dest='waste_1')

    # Wash twice with ethanol:
    air_gap = p300_multi.max_volume * 0.1

    for count in range(2):
        protocol.comment('\nEthanol #%i' % (count + 1))

        _distribute_reagent(p300_multi, reag_plt, dst_plt, [1],
                            'ethanol_%i' % (count + 1),
                            150,
                            return_tip=count == 0, air_gap=air_gap, top=0,
                            blow_out=True)

        protocol.delay(seconds=17)

        protocol.comment('\nEthanol waste #%i' % (count + 1))
        _to_waste(p300_multi, dst_plt, reag_plt, 250, dirty_tip,
                  air_gap=air_gap,
                  dest='waste_%i' % (count + 1))

    # Dry:
    protocol.delay(seconds=30)

    # Disengage MagDeck
    mag_deck.disengage()

    # Resuspend in water:
    protocol.comment('\nResuspend in water')
    _transfer_reagent(p300_multi, reag_plt, dst_plt, 1, 'water', 20,
                      mix_after=(10, 20))

    # Incubate:
    protocol.delay(minutes=2)

    # Elute:
    mag_deck.engage(height=engage_height)
    protocol.delay(minutes=3)  # "Until eluate is clear and colourless"

    # Transfer clean product to a new well (move from col 1 to col 7, etc.):
    protocol.comment('\nTransfer clean product')
    _transfer_samples(p300_multi, dst_plt, dst_plt, 1, 7, 15)

    # Disengage MagDeck:
    mag_deck.disengage()


def _cleanup_pool(p300_multi, src_plt, dst_plt):
    '''Cleanup pool A and B step.'''
    start_tip = [rack.next_tip() for rack in p300_multi.tip_racks][0]
    tip = start_tip

    for col_idx in range(int(_get_num_cols() // 2)):
        p300_multi.consolidate(
            25,
            [src_plt.columns()[idx] for idx in [col_idx, col_idx + 6]],
            dst_plt.columns()[col_idx],
            mix_after=(3, 50.0),
            trash=False,
            disposal_volume=0)

        tip = tip.parent.rows_by_name()['A'][int(tip.display_name[1])]
        p300_multi.starting_tip = tip

    return start_tip


def _incubate(therm_mod, block_temp, minutes, seconds=0, lid_temp=None):
    '''Incubate.'''
    if lid_temp and therm_mod.lid_temperature != lid_temp:
        therm_mod.set_lid_temperature(lid_temp)

    therm_mod.set_block_temperature(block_temp,
                                    hold_time_minutes=minutes,
                                    hold_time_seconds=seconds)


def _to_waste(p300_multi, src_plt, waste_plt, vol, start_tip, dest, air_gap=0):
    '''Move to waste.'''
    _, waste = _get_plate_well(waste_plt, dest)

    tip = start_tip
    p300_multi.starting_tip = tip

    for col_idx in range(_get_num_cols()):
        p300_multi.transfer(
            vol,
            src_plt.columns()[col_idx],
            waste_plt[waste].top(),
            trash=False,
            disposal_volume=0,
            air_gap=air_gap,
            blow_out=True)

        tip = tip.parent.rows_by_name()['A'][int(tip.display_name[1])]
        p300_multi.starting_tip = tip


def _transfer_samples(pipette, src_plt, dst_plt, src_col, dst_col, vol):
    '''Transfer samples.'''
    num_cols = _get_num_cols()

    for src, dst in zip(
            src_plt.columns()[src_col - 1:src_col - 1 + num_cols],
            dst_plt.columns()[dst_col - 1:dst_col - 1 + num_cols]):
        pipette.transfer(vol, src, dst, mix_after=(3, vol), disposal_volume=0)


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
                       air_gap=air_gap,
                       blow_out=blow_out)

    if return_tip:
        pipette.return_tip()
    else:
        pipette.drop_tip()


def _transfer_reagent(pipette, reag_plt, dst_plt, dst_col, reagent, vol,
                      mix_after=None):
    '''Transfer reagent.'''
    if not mix_after:
        mix_after = (3, vol)

    _, reag_well = _get_plate_well(reag_plt, reagent)

    for dst in dst_plt.columns()[dst_col - 1:dst_col - 1 + _get_num_cols()]:
        pipette.transfer(vol,
                         reag_plt[reag_well],
                         dst,
                         mix_after=mix_after,
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
    return int(_SAMPLE_PLATE['last'][1:])


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
