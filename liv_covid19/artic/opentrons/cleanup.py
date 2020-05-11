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
    'type': '4titude_96_wellplate_2200ul',
    'components': {'beads': 'A5',
                   'ethanol_1': 'A6',
                   'ethanol_2': 'A7',
                   'water': 'A8',
                   'waste_1': 'A10',
                   'waste_2': 'A11',
                   'waste_3': 'A12'}
}

_SAMPLE_PLATE_TYPE = '4titude_96_wellplate_200ul'

_SAMPLE_PLATE_LAST = 'H12'

_MAG_PLATE = {
    'type': '4titude_96_wellplate_200ul'
}


def run(protocol):
    '''Run protocol.'''
    # Setup:
    temp_deck, mag_deck, p300_multi, tip_racks_200, reag_plt, src_plts, \
        mag_plt = _setup(protocol)

    # Cleanup:
    _cleanup(protocol, temp_deck, mag_deck, p300_multi, tip_racks_200,
             reag_plt, src_plts, mag_plt,
             engage_height=mag_plt._dimensions['zDimension'])


def _setup(protocol):
    '''Setup.'''
    # Add temp deck:
    therm_mod = protocol.load_module('thermocycler', 7)
    therm_mod.open_lid()
    therm_mod.set_block_temperature(4)
    therm_mod.set_lid_temperature(105)

    temp_deck = protocol.load_module('tempdeck', 4)
    temp_deck.set_temperature(4)

    mag_deck = protocol.load_module('magdeck', 1)

    # Setup tip racks:
    tip_racks_200 = \
        {slot: protocol.load_labware('opentrons_96_filtertiprack_200ul', slot)
         for slot in [6, 9, 3, 2]}

    # Add pipettes:
    p300_multi = protocol.load_instrument(
        'p300_multi', 'right',
        tip_racks=list(tip_racks_200.values()))

    # Add reagent plate:
    reag_plt = protocol.load_labware(_REAGENT_PLATE['type'], 5)

    # Add source, thermo and mag plates:
    src_plts = [therm_mod.load_labware(_SAMPLE_PLATE_TYPE, 'PCR')]
    mag_plt = mag_deck.load_labware(_MAG_PLATE['type'], 'PCR_clean')
    # clean_plt = protocol.load_labware(_SAMPLE_PLATE_TYPE, 2, 'final_clean')

    if _get_num_cols() > 6:
        src_plts.append(temp_deck.load_labware(_SAMPLE_PLATE_TYPE, 'PCR2'))

    return temp_deck, mag_deck, p300_multi, tip_racks_200, \
        reag_plt, src_plts, mag_plt


def _cleanup(protocol, temp_deck, mag_deck, p300_multi, tip_racks_200,
             reag_plt, src_plts, mag_plt, engage_height):
    '''Clean-up.'''
    protocol.comment('\nClean-up')

    # Add beads:
    protocol.comment('\nAdd beads')

    # Slow flow rates:
    old_aspirate, old_dispense, _ = \
        _set_flow_rate(protocol, p300_multi, aspirate=50, dispense=100)

    # Rack 6:
    p300_multi.starting_tip = tip_racks_200[6].rows_by_name()['A'][2]

    _distribute_reagent(p300_multi, reag_plt, [mag_plt], 1, _get_num_cols(),
                        'beads', 50, mix_before=(5, 150), shake_before=(3, 10))

    _set_flow_rate(protocol, p300_multi,
                   aspirate=old_aspirate, dispense=old_dispense)

    # Combine Pool A and Pool B:
    protocol.comment('\nCombine Pool A and Pool B')

    # Rack 2:
    p300_multi.starting_tip = tip_racks_200[2].wells()[0]
    _combine(p300_multi, src_plts, mag_plt)

    # Incubate 10 minutes:
    protocol.delay(minutes=10)

    # Engage MagDeck:
    mag_deck.engage(height=engage_height)
    protocol.delay(minutes=5)

    # Slow flow rates:
    _set_flow_rate(protocol, p300_multi, aspirate=25, dispense=150)

    # Remove supernatant from magnetic beads:
    protocol.comment('\nRemove supernatant')

    # Rack 2:
    p300_multi.starting_tip = tip_racks_200[2].wells()[0]

    _to_waste(p300_multi, mag_plt, reag_plt, 120, tip_fate='return',
              dest='waste_1')

    # Wash twice with ethanol:
    for count in range(2):
        protocol.comment('\nEthanol #%i' % (count + 1))

        # Rack 6:
        p300_multi.starting_tip = tip_racks_200[6].rows_by_name()['A'][3]

        _distribute_reagent(p300_multi, reag_plt, [mag_plt],
                            1, _get_num_cols(),
                            'ethanol_%i' % (count + 1),
                            150,
                            disp_top=0,
                            tip_fate='return' if count == 0 else 'drop',
                            blow_out=True)

        protocol.delay(seconds=17)

        protocol.comment('\nEthanol waste #%i' % (count + 1))

        # Rack 2:
        p300_multi.starting_tip = tip_racks_200[2].wells()[0]

        _to_waste(p300_multi, mag_plt, reag_plt, 250,
                  tip_fate='return' if count == 0 else 'drop',
                  dest='waste_%i' % (count + 2))

    # Dry:
    protocol.delay(seconds=30)

    # Disengage MagDeck
    mag_deck.disengage()

    # Resuspend in water:
    protocol.comment('\nResuspend in water')

    # Rack 3:
    p300_multi.starting_tip = tip_racks_200[3].wells()[0]

    _transfer_reagent(p300_multi, reag_plt, mag_plt, 1, 'water', 20,
                      mix_after=(10, 20))

    # Incubate:
    protocol.delay(minutes=2)

    # Manually update deck?
    if _get_num_cols() > 6:

        protocol.pause('''
            Remove %s.
            Add new %s to %s.
        ''' % (src_plts[-1],
               _SAMPLE_PLATE_TYPE, temp_deck.labware.parent._display_name))

        clean_plt = src_plts[-1]
    else:
        clean_plt = temp_deck.load_labware(_SAMPLE_PLATE_TYPE)

    clean_plt.name = 'final_clean'

    # Elute:
    mag_deck.engage(height=engage_height)
    protocol.delay(minutes=3)  # "Until eluate is clear and colourless"

    # Transfer clean product to a new plate:
    protocol.comment('\nTransfer clean product')

    # Rack 9:
    p300_multi.starting_tip = tip_racks_200[9].wells()[0]

    _transfer_samples(p300_multi, mag_plt, clean_plt, 1, 1, 15)

    # Disengage MagDeck:
    mag_deck.disengage()


def _combine(p300_multi, src_plts, dst_plt):
    '''Pool A and B step.'''
    tip = p300_multi.starting_tip
    num_cols = _get_num_cols()

    for src_plt_idx, src_plt in enumerate(src_plts):
        for col_idx in range(int(num_cols // 2)):
            p300_multi.consolidate(
                25,
                [src_plt.columns()[idx] for idx in [col_idx, col_idx + 6]],
                dst_plt.columns()[col_idx + (src_plt_idx * 6)],
                mix_after=(3, 50.0),
                trash=False,
                disposal_volume=0)

            tip = _next_tip(tip)
            p300_multi.starting_tip = tip


def _incubate(therm_mod, block_temp, minutes, seconds=0, lid_temp=None):
    '''Incubate.'''
    if lid_temp and therm_mod.lid_temperature != lid_temp:
        therm_mod.set_lid_temperature(lid_temp)

    therm_mod.set_block_temperature(block_temp,
                                    hold_time_minutes=minutes,
                                    hold_time_seconds=seconds)


def _to_waste(p300_multi, src_plt, waste_plt, vol, dest, tip_fate='return'):
    '''Move to waste.'''
    _, waste = _get_plate_well(waste_plt, dest)

    tip = p300_multi.starting_tip

    for col_idx in range(_get_num_cols()):
        p300_multi.pick_up_tip()

        max_vol = p300_multi._last_tip_picked_up_from.max_volume

        for _ in range(vol // max_vol):
            _to_waste_aliquot(p300_multi,
                              src_plt.columns()[col_idx][0],
                              waste_plt[waste].top(),
                              max_vol)

        vol_remain = vol % max_vol

        if vol_remain:
            _to_waste_aliquot(p300_multi,
                              src_plt.columns()[col_idx][0],
                              waste_plt[waste].top(),
                              vol_remain)

        if tip_fate == 'drop':
            p300_multi.drop_tip()
        elif tip_fate == 'return':
            p300_multi.return_tip()

        tip = _next_tip(tip)
        p300_multi.starting_tip = tip


def _next_tip(tip):
    '''Get next tip.'''
    try:
        tip_idx = int(tip.display_name.split()[0][1:])
        tip = tip.parent.rows_by_name()['A'][tip_idx]
    except IndexError:
        # End of plate...
        tip = None

    return tip


def _to_waste_aliquot(pipette, src_well, waste_well, vol):
    '''Move aliquot to waste.'''
    pipette.aspirate(vol, src_well)
    pipette.dispense(vol, waste_well)
    pipette.blow_out(waste_well)


def _transfer_samples(pipette, src_plt, dst_plt, src_col, dst_col, vol):
    '''Transfer samples.'''
    num_cols = _get_num_cols()

    for src, dst in zip(
            src_plt.columns()[src_col - 1:src_col - 1 + num_cols],
            dst_plt.columns()[dst_col - 1:dst_col - 1 + num_cols]):
        pipette.transfer(vol, src, dst, disposal_volume=0)


def _distribute_reagent(pipette, reag_plt,
                        dst_plts, dst_col_start, dst_col_num,
                        reagent, vol,
                        tip_fate='drop',
                        mix_before=None,
                        shake_before=None,
                        asp_top=None, asp_bottom=None,
                        disp_top=None, disp_bottom=None,
                        blow_out=False):
    '''Distribute reagent.'''
    if not pipette.hw_pipette['has_tip']:
        pipette.pick_up_tip()

    _, reag_well = _get_plate_well(reag_plt, reagent)

    dest_cols = []

    for dst_plt in dst_plts:
        dest_cols.extend(dst_plt.rows_by_name()['A'][
            dst_col_start - 1:dst_col_start - 1 + dst_col_num])

    asp_well = reag_plt.wells_by_name()[reag_well]

    _distribute(pipette,
                asp_well.top(asp_top) if asp_top is not None
                else (asp_well.bottom(asp_bottom)
                      if asp_bottom is not None
                      else asp_well),
                [well.top(disp_top) if disp_top is not None
                 else (well.bottom(disp_bottom)
                       if disp_bottom is not None
                       else well)
                 for well in dest_cols],
                vol,
                mix_before,
                shake_before,
                blow_out)

    if tip_fate == 'drop':
        pipette.drop_tip()
    elif tip_fate == 'return':
        pipette.return_tip()


def _distribute(pipette, asp_pos, disp_pos, vol, mix_before, shake_before,
                blow_out):
    '''Distribute.'''
    max_asps = int(pipette._last_tip_picked_up_from.max_volume // vol)

    aliquot_disps = [disp_pos[i:i + max_asps]
                     for i in range(0, len(disp_pos), max_asps)]

    for aliquot_disp in aliquot_disps:
        # Mix:
        if mix_before:
            pipette.mix(*mix_before, asp_pos)

        # Aspirate:
        asp_vol = vol * len(aliquot_disp)
        pipette.aspirate(asp_vol, asp_pos)

        # Shake:
        if shake_before:
            for _ in range(shake_before[0]):
                pipette.move_to(asp_pos.top(shake_before[1]))
                pipette.move_to(asp_pos.top())

        # Dispense:
        for pos in aliquot_disp:
            pipette.dispense(vol, pos)

        # Blow-out:
        if blow_out:
            pipette.blow_out()


def _transfer_reagent(pipette, reag_plt, dst_plt, dst_col, reagent, vol,
                      mix_after=None):
    '''Transfer reagent.'''
    if not mix_after:
        mix_after = (3, vol)

    _, reag_well = _get_plate_well(reag_plt, reagent)

    num_cols = _get_num_cols()

    for dst in dst_plt.columns()[dst_col - 1:dst_col - 1 + num_cols]:
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
    return int(_SAMPLE_PLATE_LAST[1:])


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
