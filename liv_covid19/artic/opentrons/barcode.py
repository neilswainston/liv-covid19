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
    'H6': 1
}


def run(protocol):
    '''Run protocol.'''
    # Setup:
    therm_mod, p10_multi, reag_plt, src_plt, dst_plt = _setup(protocol)

    # Barcode ligation:
    _barcode(protocol, therm_mod, p10_multi, reag_plt, src_plt, dst_plt)


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
    p300_multi = protocol.load_instrument(
        'p300_multi', 'right', tip_racks=tip_racks_10)

    # Add reagent plate:
    reag_plt = protocol.load_labware(_REAGENT_PLATE['type'], 5)

    # Add source, thermo and mag plates:
    src_plt = temp_deck.load_labware(_SAMPLE_PLATE['type'], 'src_plt')
    therm_plt = therm_mod.load_labware(_SAMPLE_PLATE['type'], 'dst_plt')

    return therm_mod, p300_multi, reag_plt, src_plt, therm_plt


def _barcode(protocol, therm_mod, p10_multi, reag_plt, src_plt, dst_plt):
    '''Barcode.'''
    protocol.comment('\nBarcode samples')

    # Add water:
    protocol.comment('\nAdd water')

    _distribute_reagent(p10_multi, reag_plt, dst_plt, [1], 'water', 5.5,
                        return_tip=True)

    # Add DNA:
    protocol.comment('\nAdd DNA')

    _transfer_samples(p10_multi, src_plt, dst_plt, 1, 1, 1.5)

    # Add barcodes:
    protocol.comment('\nAdd barcodes')

    for barcode_idx in [0, 1, 2]:
        col_idxs = [idx + 1 for idx in range(barcode_idx, _get_num_cols(), 3)]

        _distribute_barcodes(p10_multi, reag_plt, dst_plt, col_idxs,
                             'barcodes_%i' % (barcode_idx + 1), 2.5)

    # Add ligation mastermix:
    protocol.comment('\nAdd ligation mastermix')

    _distribute_reagent(p10_multi, reag_plt, dst_plt, [1],
                        'ligation_mastermix', 10, top=0)

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


def _distribute_barcodes(pipette, reag_plt, dst_plt, dst_cols, reagent, vol):
    '''Distribute barcodes.'''
    pipette.pick_up_tip()

    _, reag_well = _get_plate_well(reag_plt, reagent)

    dest_cols = [dst_plt.rows_by_name()['A'][col_idx - 1]
                 for col_idx in dst_cols]

    pipette.distribute(vol,
                       reag_plt.wells_by_name()[reag_well],
                       [well.top() for well in dest_cols],
                       new_tip='never',
                       disposal_volume=0)

    pipette.drop_tip()


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
    return int(list(_DNA_VOLS.keys())[-1][1])


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
