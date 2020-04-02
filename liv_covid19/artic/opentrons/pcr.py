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
    'components': {'primer_pool_a_mastermix': 'A3',
                   'primer_pool_b_mastermix': 'A4'}
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
    therm_mod, p10_multi, p300_multi, reag_plt, src_plts, therm_plts = \
        _setup(protocol)

    therm_mod.set_block_temperature(4)

    # PCR:
    _pcr(protocol, therm_mod, p10_multi, p300_multi, reag_plt, src_plts,
         therm_plts)


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

    tip_racks_200 = \
        [protocol.load_labware('opentrons_96_filtertiprack_200ul', slot)
         for slot in [6, 9]]

    # Add pipettes:
    p10_multi = protocol.load_instrument(
        'p10_multi', 'left', tip_racks=tip_racks_10)

    p300_multi = protocol.load_instrument(
        'p300_multi', 'right', tip_racks=tip_racks_200)

    # Add reagent plate:
    reag_plt = protocol.load_labware(_REAGENT_PLATE['type'], 5, 'Reagents')

    # Add source and thermo plates:
    src_plts = [temp_deck.load_labware(_SAMPLE_PLATE['type'], 'cDNA')]
    therm_plts = [therm_mod.load_labware(_SAMPLE_PLATE['type'], 'PCR')]

    return therm_mod, p10_multi, p300_multi, reag_plt, src_plts, therm_plts


def _pcr(protocol, therm_mod, p10_multi, p300_multi, reag_plt, src_plts,
         dst_plts):
    '''Do PCR.'''
    protocol.comment('\nSetup PCR')

    # Add PCR primer mix:
    protocol.comment('\nAdd PCR primer mix')

    prev_aspirate, _, _ = _set_flow_rate(protocol, p300_multi, aspirate=50)

    # Add Pool A:
    _distribute_reagent(p300_multi, reag_plt, dst_plts, [1],
                        'primer_pool_a_mastermix', 22.5, bottom=1.5)

    # Add Pool B:
    _distribute_reagent(p300_multi, reag_plt, dst_plts, [7],
                        'primer_pool_b_mastermix', 22.5, bottom=1.5)

    _set_flow_rate(protocol, p300_multi, aspirate=prev_aspirate)

    # Add samples to each pool:
    protocol.comment('\nSplit samples into pools A and B')

    for plt_idx, (src_plt, dst_plt) in enumerate(zip(src_plts, dst_plts)):
        for col_idx in range(_get_num_cols()[plt_idx]):
            p10_multi.distribute(
                2.5,
                src_plt.columns()[col_idx],
                [dst_plt.columns()[idx] for idx in [col_idx, col_idx + 6]],
                mix_after=(3, 2.5),
                disposal_volume=0)

    # PCR:
    protocol.comment('\nPerform PCR')
    _do_pcr(therm_mod)

    # Incubate at 8C for 1 minute:
    _incubate(therm_mod, 8, 1)


def _do_pcr(therm_mod):
    '''Do PCR.'''
    therm_mod.close_lid()
    therm_mod.set_lid_temperature(105)
    therm_mod.set_block_temperature(98, hold_time_seconds=30)

    profile = [
        {'temperature': 98, 'hold_time_seconds': 15},
        {'temperature': 65, 'hold_time_seconds': 5}
    ]

    therm_mod.execute_profile(steps=profile, repetitions=30,
                              block_max_volume=25)

    therm_mod.open_lid()


def _incubate(therm_mod, block_temp, minutes, seconds=0, lid_temp=None):
    '''Incubate.'''
    if lid_temp and therm_mod.lid_temperature != lid_temp:
        therm_mod.set_lid_temperature(lid_temp)

    therm_mod.set_block_temperature(block_temp,
                                    hold_time_minutes=minutes,
                                    hold_time_seconds=seconds)


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