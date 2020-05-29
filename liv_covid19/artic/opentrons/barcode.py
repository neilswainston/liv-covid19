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


metadata = {'apiLevel': '2.3',
            'author': 'Neil Swainston <neil.swainston@liverpool.ac.uk>'}

_REAGENT_PLATE = {
    'type': '4titude_96_wellplate_200ul',
    'components': {'barcodes_1': 'A1',
                   'barcodes_2': 'A2',
                   'barcodes_3': 'A3',
                   'ligation_mastermix': 'A4',
                   'water': 'A5'}
}

_SAMPLE_PLATE_TYPE = '4titude_96_wellplate_200ul'

_SAMPLE_PLATE_LAST = 'H12'

_POOL_PLATE = {
    'type': 'opentrons_24_tuberack_eppendorf_1.5ml_safelock_snapcap'
}

_TEMP_DECK = 'tempdeck'


def run(protocol):
    '''Run protocol.'''
    # Setup:
    therm_mod, p10_multi, p300_multi, reag_plt, src_plt, dst_plt, \
        pool_plt = _setup(protocol)

    # Set to next clean tip:
    # next_tip_10 = p10_multi.tip_racks[0].rows_by_name()['A'][2]
    # p10_multi.starting_tip = next_tip_10

    # Barcode ligation:
    _barcode(protocol, therm_mod, p10_multi, reag_plt, src_plt, dst_plt)

    # Pool barcodes:
    _barcode_pool(protocol, p300_multi, dst_plt, pool_plt)


def _setup(protocol):
    '''Setup.'''
    # Add temp deck:
    therm_mod = protocol.load_module('thermocycler', 7)
    therm_mod.open_lid()
    therm_mod.set_block_temperature(4)
    therm_mod.set_lid_temperature(105)

    temp_deck = protocol.load_module(_TEMP_DECK, 4)
    temp_deck.set_temperature(4)

    # Setup tip racks:
    tip_racks_10 = \
        [protocol.load_labware('opentrons_96_filtertiprack_10ul', slot)
         for slot in [1, 2, 3]]

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
    src_plt = temp_deck.load_labware(_SAMPLE_PLATE_TYPE, 'PCR_normal')
    therm_plt = therm_mod.load_labware(_SAMPLE_PLATE_TYPE, 'PCR_barcode')
    pool_plt = protocol.load_labware(_POOL_PLATE['type'], 9, 'barcode_pool')

    return therm_mod, p10_multi, p300_multi, reag_plt, src_plt, therm_plt, \
        pool_plt


def _barcode(protocol, therm_mod, p10_multi, reag_plt, src_plt, dst_plt):
    '''Barcode.'''
    protocol.comment('\nBarcode samples')

    # Add water:
    protocol.comment('\nAdd water')

    _distribute_reagent(p10_multi, reag_plt,
                        [dst_plt], 1, _get_num_cols(),
                        'water', 6.0,
                        tip_fate=None)

    # Add barcodes:
    protocol.comment('\nAdd barcodes')

    for barcode_idx in range(min(3, _get_num_cols())):
        col_idxs = [idx + 1 for idx in range(barcode_idx, _get_num_cols(), 3)]

        _distribute_barcodes(p10_multi, reag_plt, dst_plt, col_idxs,
                             'barcodes_%i' % (barcode_idx + 1), 2.5)

    # Add DNA:
    protocol.comment('\nAdd DNA')

    _transfer_samples(p10_multi, src_plt, dst_plt, 1, 1, 1.5)

    # Add ligation mastermix:
    protocol.comment('\nAdd ligation mastermix')

    prev_aspirate, prev_dispense, _ = \
        _set_flow_rate(protocol, p10_multi, aspirate=3, dispense=5)

    _transfer_reagent(p10_multi, reag_plt, dst_plt,
                      1, 'ligation_mastermix', 10)

    _set_flow_rate(protocol, p10_multi, aspirate=prev_aspirate,
                   dispense=prev_dispense)

    # Incubate at 20C for 5 minute:
    therm_mod.close_lid()
    _incubate(therm_mod, 20, 5, lid_temp=105)

    # Incubate at 65C for 5 minute:
    _incubate(therm_mod, 65, 5, lid_temp=105)

    therm_mod.set_block_temperature(4)
    therm_mod.open_lid()


def _barcode_pool(protocol, p300_multi, src_plt, dst_plt):
    '''Pool.'''
    protocol.comment('\nPooling barcoded samples')

    vol = 20.0

    # Bottom rows of tip-rack:
    for idx, col_idx in enumerate(range(0, _get_num_cols(), 3)):
        p300_multi.pick_up_tip(p300_multi.tip_racks[0].wells()[-1 - idx],
                               presses=1, increment=0)

        for col in src_plt.columns()[col_idx:col_idx + 3]:
            for well in col:
                # z corresponds to mm above the well bottom:
                p300_multi.aspirate(vol, well.bottom(z=0))

            p300_multi.dispense(vol * len(col), dst_plt.wells()[idx])

        p300_multi.drop_tip()


def _incubate(therm_mod, block_temp, minutes, seconds=0, lid_temp=None):
    '''Incubate.'''
    if lid_temp and therm_mod.lid_temperature != lid_temp:
        therm_mod.set_lid_temperature(lid_temp)

    therm_mod.set_block_temperature(block_temp,
                                    hold_time_minutes=minutes,
                                    hold_time_seconds=seconds)


def _transfer_samples(pipette, src_plt, dst_plt, src_col, dst_col, vol):
    '''Transfer samples.'''
    num_cols = _get_num_cols()

    for src, dst in zip(
            src_plt.columns()[src_col - 1:src_col - 1 + num_cols],
            dst_plt.columns()[dst_col - 1:dst_col - 1 + num_cols]):

        if not pipette.hw_pipette['has_tip']:
            pipette.pick_up_tip()

        pipette.aspirate(vol, src[0])
        pipette.dispense(vol, dst[0])
        pipette.mix(3, vol)
        pipette.drop_tip()


def _distribute_barcodes(pipette, reag_plt, dst_plt, dst_cols, reagent, vol):
    '''Distribute barcodes.'''
    if not pipette.hw_pipette['has_tip']:
        pipette.pick_up_tip()

    _, reag_well = _get_plate_well(reag_plt, reagent)

    dest_cols = [dst_plt.rows_by_name()['A'][col_idx - 1]
                 for col_idx in dst_cols]

    pipette.distribute(vol,
                       reag_plt.wells_by_name()[reag_well],
                       dest_cols,
                       new_tip='never',
                       disposal_volume=0)

    pipette.drop_tip()


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
    # else retain for reuse


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
