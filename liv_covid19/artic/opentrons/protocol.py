'''
(c) University of Liverpool 2020

All rights reserved.

@author: neilswainston
'''
# pylint: disable=invalid-name
# pylint: disable=too-many-arguments
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
                   'primer_pool_b_mastermix': 'A4'}
}

_PLATE = {
    'type': '4titude_96_wellplate_200ul',
    'last': 'H2'
}


def run(protocol):
    '''Run protocol.'''
    # Setup:
    therm_mod, mag_deck, p10_multi, p50_multi, reag_plt, src_plt, therm_plt, \
        mag_plt = _setup(protocol)

    # cDNA:
    _cdna(protocol, therm_mod, p10_multi, p50_multi, reag_plt, src_plt,
          therm_plt)

    therm_mod.set_block_temperature(4)

    protocol.pause()

    # PCR:
    _pcr(protocol, therm_mod, p10_multi, p50_multi, reag_plt, src_plt,
         therm_plt)

    protocol.pause()

    # Cleanup:
    _cleanup(protocol, therm_mod, mag_deck, p10_multi, p50_multi, reag_plt,
             therm_plt, mag_plt)


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
    tip_racks_10 = \
        [protocol.load_labware('opentrons_96_filtertiprack_10ul', slot)
         for slot in [3, 6]]

    tip_racks_200 = \
        [protocol.load_labware('opentrons_96_filtertiprack_200ul', slot)
         for slot in [2]]

    # Add pipettes:
    p10_multi = protocol.load_instrument(
        'p10_multi', 'left', tip_racks=tip_racks_10)

    p50_multi = protocol.load_instrument(
        'p50_multi', 'right', tip_racks=tip_racks_200)

    # Add reagent plate:
    reag_plt = protocol.load_labware(_REAGENT_PLATE['type'], 5)

    # Add source, thermo and mag plates:
    src_plt = temp_deck.load_labware(_PLATE['type'], 'src_plt')
    therm_plt = therm_mod.load_labware(_PLATE['type'], 'dst_plt')
    mag_plt = mag_deck.load_labware(_PLATE['type'], 'dst_plt')

    return therm_mod, mag_deck, p10_multi, p50_multi, reag_plt, src_plt, \
        therm_plt, mag_plt


def _cdna(protocol, therm_mod, p10_multi, p50_multi, reag_plt, src_plt,
          dst_plt):
    '''Generate cDNA.'''
    # Add primer mix:
    protocol.comment('\nAdd primer mix')
    _distribute_reagent(p50_multi, reag_plt, dst_plt, 1, 'primer_mix', 8.0)

    # Add RNA samples:
    protocol.comment('\nAdd RNA samples')
    _transfer_samples(p10_multi, src_plt, dst_plt, 1, 1, 5.0)

    # Incubate at 65C for 5 minute:
    therm_mod.close_lid()
    _incubate(therm_mod, 65, 5, lid_temp=105)

    # Incubate (on ice) / at min temp for 1 minute:
    _incubate(therm_mod, 4, 1)
    therm_mod.open_lid()

    # Add RT reaction mix:
    protocol.comment('\nAdd RT reaction mix')
    _transfer_reagent(p10_multi, reag_plt, dst_plt, 1, 'rt_reaction_mix', 7.0)

    # Incubate at 42C for 10 minute:
    therm_mod.close_lid()
    _incubate(therm_mod, 42, 50, lid_temp=105)

    # Incubate at 70C for 10 minute:
    _incubate(therm_mod, 70, 10, lid_temp=105)

    # Incubate at 4C for 1 minute:
    _incubate(therm_mod, 4, 1, lid_temp=105)
    therm_mod.open_lid()


def _pcr(protocol, therm_mod, p10_multi, p50_multi, reag_plt, src_plt,
         dst_plt):
    '''Do PCR.'''
    # Add PCR primer mix:
    protocol.comment('\nAdd PCR primer mix')

    # Add Pool A:
    _distribute_reagent(p50_multi, reag_plt, dst_plt, 1,
                        'primer_pool_a_mastermix', 22.5)

    # Add Pool B:
    _distribute_reagent(p50_multi, reag_plt, dst_plt, 7,
                        'primer_pool_b_mastermix', 22.5)

    # Add samples to each pool:
    _transfer_samples(p10_multi, src_plt, dst_plt, 1, 1, 2.5)
    _transfer_samples(p10_multi, src_plt, dst_plt, 1, 7, 2.5)

    # PCR:
    protocol.comment('\nPerforming PCR')
    _do_pcr(therm_mod)

    # Incubate at 4C for 1 minute:
    _incubate(therm_mod, 4, 1)


def _cleanup(protocol, therm_mod, mag_deck, p10_multi, p50_multi, reag_plt,
             src_plt, dst_plt):
    '''Clean-up.'''
    # Combine Pool A and Pool B:
    protocol.comment('\nCombining Pools A and B')

    for col_idx in range(_get_num_cols()):
        p50_multi.consolidate(
            25,
            [src_plt.columns()[idx] for idx in [col_idx, col_idx + 6]],
            dst_plt.columns()[col_idx])

    # Disengage MagDeck
    mag_deck.disengage()


def _incubate(therm_mod, block_temp, minutes, seconds=0, lid_temp=None):
    '''Incubate.'''
    if lid_temp:
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
        pipette.transfer(vol, src, dst, mix_after=(1, 5.0))


def _distribute_reagent(pipette, reag_plt, dst_plt, dst_col, reagent, vol):
    '''Distribute reagent.'''
    pipette.pick_up_tip()

    _, reag_well = _get_plate_well(reag_plt, reagent)

    dest_cols = dst_plt.rows_by_name()['A']

    pipette.distribute(vol,
                       reag_plt.wells_by_name()[reag_well],
                       dest_cols[dst_col - 1:dst_col - 1 + _get_num_cols()],
                       new_tip='never')

    pipette.drop_tip()


def _transfer_reagent(pipette, reag_plt, dst_plt, dst_col, reagent, vol):
    '''Transfer reagent.'''
    _, reag_well = _get_plate_well(reag_plt, reagent)

    for dst in dst_plt.columns()[dst_col - 1:dst_col - 1 + _get_num_cols()]:
        pipette.transfer(vol, reag_plt[reag_well], dst, mix_after=(1, vol))


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


def _get_num_cols():
    '''Get number of sample columns.'''
    return int(_PLATE['last'][1])


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
