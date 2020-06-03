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
    'components': {'water': 'A8',
                   'endprep_mastermix': 'A9'}
}

_SAMPLE_PLATE_TYPE = '4titude_96_wellplate_200ul'

_SAMPLE_PLATE_LAST = 'H12'

_DNA_VOLS = {'A1': 3, 'H12': 1}

_TEMP_DECK = 'tempdeck'

_VOLS = {
    'endprep_mastermix': 7.5,
    'water_dna': 7.5
}


def run(protocol):
    '''Run protocol.'''
    # Setup:
    therm_mod, p10_multi, reag_plt, src_plt, dst_plt = _setup(protocol)

    # Normalise DNA concentrations:
    _normalise(protocol, therm_mod, p10_multi, reag_plt, src_plt, dst_plt)


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
         for slot in [9, 6]]

    # Add pipettes:
    p10_multi = protocol.load_instrument(
        'p10_multi', 'left', tip_racks=tip_racks_10)

    # Add reagent plate:
    reag_plt = protocol.load_labware(_REAGENT_PLATE['type'], 5)

    # Add source, thermo and mag plates:
    src_plt = temp_deck.load_labware(_SAMPLE_PLATE_TYPE, 'PCR_clean')
    therm_plt = therm_mod.load_labware(_SAMPLE_PLATE_TYPE, 'PCR_normal')

    return therm_mod, p10_multi, reag_plt, src_plt, therm_plt


def _normalise(protocol, therm_mod, p10_multi, reag_plt, src_plt, dst_plt):
    '''Generate cDNA.'''
    protocol.comment('\nNormalise DNA concentrations')

    # Add endprep mastermix:
    _distribute_reagent(p10_multi, reag_plt, [dst_plt], 1, _get_num_cols(),
                        'endprep_mastermix', _VOLS['endprep_mastermix'])

    # Add water and DNA:
    _, reag_well = _get_plate_well(reag_plt, 'water')

    protocol.comment('\nAdd water and DNA')

    for idx, (well, vol) in enumerate(_DNA_VOLS.items()):
        p10_multi.pick_up_tip(p10_multi.tip_racks[-1].wells()[-1 - idx],
                              presses=1, increment=0)

        p10_multi.aspirate(_VOLS['water_dna'] - vol, reag_plt[reag_well])
        p10_multi.aspirate(vol, src_plt[well])
        p10_multi.dispense(_VOLS['water_dna'], dst_plt[well])
        p10_multi.mix(3, _VOLS['water_dna'])

        p10_multi.drop_tip()

    # Incubate at 20C for 5 minute:
    therm_mod.close_lid()
    _incubate(therm_mod, 20, 5, lid_temp=105)

    # Incubate at 65C for 5 minute:
    _incubate(therm_mod, 65, 5, lid_temp=105)

    therm_mod.set_block_temperature(4)
    therm_mod.open_lid()


def _incubate(therm_mod, block_temp, minutes, seconds=0, lid_temp=None):
    '''Incubate.'''
    if lid_temp and therm_mod.lid_temperature != lid_temp:
        therm_mod.set_lid_temperature(lid_temp)

    therm_mod.set_block_temperature(block_temp,
                                    hold_time_minutes=minutes,
                                    hold_time_seconds=seconds)


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
