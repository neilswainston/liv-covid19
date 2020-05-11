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
    'components': {'water': 'A5',
                   'endprep_mastermix': 'A6'}
}

_SAMPLE_PLATE_TYPE = '4titude_96_wellplate_200ul'

_SAMPLE_PLATE_LAST = 'H12'


def run(protocol):
    '''Run protocol.'''
    # Setup:
    therm_mod, p10_multi, p300_multi, reag_plt, src_plts, dest_plt, \
        therm_plt = _setup(protocol)

    # Set to next clean tip:
    next_tip_300 = p300_multi.tip_racks[0].rows_by_name()['A'][2]
    p300_multi.starting_tip = next_tip_300

    # Pool:
    _pool(protocol, therm_mod, p10_multi, p300_multi, reag_plt, src_plts,
          dest_plt, therm_plt)


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
         for slot in [2]]

    tip_racks_200 = \
        [protocol.load_labware('opentrons_96_filtertiprack_200ul', slot)
         for slot in [6]]

    # Add reagent plate:
    reag_plt = protocol.load_labware(_REAGENT_PLATE['type'], 5)

    # Add pipettes:
    p10_multi = protocol.load_instrument(
        'p10_multi', 'left', tip_racks=tip_racks_10)

    p300_multi = protocol.load_instrument(
        'p300_multi', 'right', tip_racks=tip_racks_200)

    # Add source, thermo and mag plates:
    src_plts = [protocol.load_labware(_SAMPLE_PLATE_TYPE, 1, 'PCR')]
    dest_plt = temp_deck.load_labware(_SAMPLE_PLATE_TYPE, 'PCR_clean')
    therm_plt = therm_mod.load_labware(_SAMPLE_PLATE_TYPE, 'PCR_normal')

    if len(_SAMPLE_PLATE_LAST) > 1:
        src_plts.append(protocol.load_labware(
            _SAMPLE_PLATE_TYPE, 9, 'PCR2'))

    return therm_mod, p10_multi, p300_multi, reag_plt, src_plts, dest_plt, \
        therm_plt


def _pool(protocol, therm_mod, p10_multi, p300_multi, reag_plt, src_plts,
          dest_plt, therm_plt):
    '''Pool.'''
    # Add water:
    protocol.comment('\nAdd water')
    _distribute_reagent(p300_multi, reag_plt,
                        [dest_plt], 1, _get_num_cols(),
                        'water', 45, tip_fate='retain')

    # Add endprep mastermix:
    protocol.comment('\nAdd endprep mastermix')

    prev_aspirate, prev_dispense, _ = \
        _set_flow_rate(protocol, p300_multi, aspirate=50, dispense=100)

    _distribute_reagent(p300_multi, reag_plt,
                        [therm_plt], 1, _get_num_cols(),
                        'endprep_mastermix', 10)

    _set_flow_rate(protocol, p300_multi, aspirate=prev_aspirate,
                   dispense=prev_dispense)

    # Combine Pool A and Pool B:
    protocol.comment('\nCombine Pool A and Pool B')
    _combine(p10_multi, src_plts, dest_plt, therm_plt)

    # Incubate at 20C for 5 minute:
    therm_mod.close_lid()
    _incubate(therm_mod, 20, 10, lid_temp=105)

    # Incubate at 65C for 5 minute:
    _incubate(therm_mod, 65, 10, lid_temp=105)
    therm_mod.open_lid()

    # Incubate at 8C for 1 minute:
    _incubate(therm_mod, 8, 1, lid_temp=105)
    therm_mod.open_lid()


def _combine(p10_multi, src_plts, dst_plt, therm_plt):
    '''Combine pools A and B .'''
    for src_plt_idx, src_plt in enumerate(src_plts):
        for col_idx in range(int(_get_num_cols() // 2)):
            # Pool, dilute and mix in PCR_clean plate:
            dst_well = dst_plt.columns()[
                col_idx + (src_plt_idx * 6)][0]
            p10_multi.pick_up_tip()
            p10_multi.aspirate(2.5, src_plt.columns()[col_idx][0])
            p10_multi.aspirate(2.5, src_plt.columns()[col_idx + 6][0])
            p10_multi.dispense(5.0, dst_well)
            p10_multi.mix(3, 10.0)

            # Transfer to PCR_normal plate on thermocycler:
            p10_multi.transfer(5.0,
                               dst_well,
                               therm_plt.columns()[
                                   col_idx + (src_plt_idx * 6)][0],
                               mix_after=(3, 10.0),
                               disposal_volume=0,
                               new_tip='never')

            p10_multi.drop_tip()


def _distribute_reagent(pipette, reag_plt,
                        dst_plts, dst_col_start, dst_col_num,
                        reagent, vol,
                        tip_fate='drop',
                        mix_before=None,
                        shake_before=None,
                        air_gap=0,
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
                air_gap,
                mix_before,
                shake_before,
                blow_out)

    if tip_fate == 'drop':
        pipette.drop_tip()
    elif tip_fate == 'return':
        pipette.return_tip()


def _distribute(pipette, asp_pos, disp_pos, vol, air_gap, mix_before,
                shake_before, blow_out):
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

        # Air-gap:
        if air_gap:
            pipette.air_gap(air_gap)

        # Shake:
        if shake_before:
            for _ in range(shake_before[0]):
                pipette.move_to(asp_pos.top(shake_before[1]))
                pipette.move_to(asp_pos.top())

        # Dispense:
        for pos in aliquot_disp:
            pipette.dispense(vol + air_gap, pos)

        # Blow-out:
        if blow_out:
            pipette.blow_out()


def _transfer_samples(pipette, src_plt, dst_plt, src_col, dst_col, vol):
    '''Transfer samples.'''
    num_cols = _get_num_cols()

    for src, dst in zip(
            src_plt.columns()[src_col - 1:src_col - 1 + num_cols],
            dst_plt.columns()[dst_col - 1:dst_col - 1 + num_cols]):
        pipette.transfer(vol, src, dst, mix_after=(3, vol), disposal_volume=0)


def _incubate(therm_mod, block_temp, minutes, seconds=0, lid_temp=None):
    '''Incubate.'''
    if lid_temp and therm_mod.lid_temperature != lid_temp:
        therm_mod.set_lid_temperature(lid_temp)

    therm_mod.set_block_temperature(block_temp,
                                    hold_time_minutes=minutes,
                                    hold_time_seconds=seconds)


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
