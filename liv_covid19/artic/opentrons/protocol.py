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

_TIP_RACK_TYPE = 'opentrons_96_filtertiprack_200ul'

_REAGENT_PLATE = {
    'type': 'nest_12_reservoir_15ml',
    'components': {'primer_mix': 'A1',
                   'rt_reaction_mix': 'A2',
                   'primer_pool_a_mastermix': 'A3',
                   'primer_pool_b_mastermix': 'A4'}
}

_SRC_PLATE = {
    'type': '4titude_96_wellplate_200ul',
    'last': 'H2'
}

_DST_PLATE = {
    'type': '4titude_96_wellplate_200ul'
}


def run(protocol):
    '''Run protocol.'''
    # Setup:
    thermo_mod, p10_multi, p50_multi, reag_plt, src_plt, dst_plt = \
        _setup(protocol)

    # Generate cDNA:
    _cdna(protocol, thermo_mod, p10_multi, p50_multi, reag_plt, src_plt,
          dst_plt)

    thermo_mod.set_block_temperature(4)

    protocol.pause()

    _pcr(protocol, thermo_mod, p10_multi, p50_multi, reag_plt, src_plt,
         dst_plt)


def _setup(protocol):
    '''Setup.'''
    # Add temp deck:
    thermo_mod = protocol.load_module('thermocycler', 7)
    thermo_mod.open_lid()
    thermo_mod.set_block_temperature(65)

    temp_deck = protocol.load_module('tempdeck', 4)
    temp_deck.set_temperature(4)

    # Setup tip racks:
    tip_racks_10 = \
        [protocol.load_labware('opentrons_96_filtertiprack_10ul', slot)
         for slot in [1, 3]]

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

    # Add source and destination plates:
    src_plt = temp_deck.load_labware(_SRC_PLATE['type'], 'src_plt')
    dst_plt = thermo_mod.load_labware(_DST_PLATE['type'], 'dst_plt')

    return thermo_mod, p10_multi, p50_multi, reag_plt, src_plt, dst_plt


def _cdna(protocol, thermo_mod, p10_multi, p50_multi, reag_plt, src_plt,
          dst_plt):
    '''Generate cDNA.'''
    # Add primer mix:
    protocol.comment('\nAdd primer mix')
    _distribute_reagent(p50_multi, reag_plt, dst_plt, 1, _get_last_col(),
                        'primer_mix', 8.0)

    # Add RNA samples:
    protocol.comment('\nAdd RNA samples')
    _add_samples(p10_multi, src_plt, dst_plt, 1, _get_last_col(), 5.0)

    # Incubate at 65C for 5 minute:
    thermo_mod.close_lid()
    _incubate(thermo_mod, 65, 5, lid_temp=105)

    # Incubate (on ice) / at min temp for 1 minute:
    _incubate(thermo_mod, 4, 1)
    thermo_mod.open_lid()

    # Add RT reaction mix:
    protocol.comment('\nAdd RT reaction mix')
    _transfer_reagent(p10_multi, reag_plt, dst_plt, 1, _get_last_col(),
                      'rt_reaction_mix', 7.0)

    # Incubate at 42C for 10 minute:
    thermo_mod.close_lid()
    _incubate(thermo_mod, 42, 50, lid_temp=105)

    # Incubate at 70C for 10 minute:
    _incubate(thermo_mod, 70, 10, lid_temp=105)

    # Incubate at 4C for 1 minute:
    _incubate(thermo_mod, 4, 1, lid_temp=4)
    thermo_mod.open_lid()


def _pcr(protocol, thermo_mod, p10_multi, p50_multi, reag_plt, src_plt,
         dst_plt):
    '''Do PCR.'''
    # Add PCR primer mix:
    protocol.comment('\nAdd PCR primer mix')

    # Add Pool A:
    _distribute_reagent(p50_multi, reag_plt, dst_plt, 1, _get_last_col(),
                        'primer_pool_a_mastermix', 22.5)

    # Add Pool B:
    _distribute_reagent(p50_multi, reag_plt, dst_plt, 7, 7 + _get_last_col(),
                        'primer_pool_b_mastermix', 22.5)

    # Add samples to each pool:
    _add_samples(p10_multi, src_plt, dst_plt, 1, _get_last_col(), 2.5)
    _add_samples(p10_multi, src_plt, dst_plt, 7, 7 + _get_last_col(), 2.5)

    # PCR:
    protocol.comment('\nPerforming PCR')
    _do_pcr(thermo_mod)

    # Incubate at 4C for 1 minute:
    _incubate(thermo_mod, 4, 1, lid_temp=4)


def _incubate(thermo_mod, block_temp, minutes, seconds=0, lid_temp=None):
    '''Incubate.'''
    if lid_temp:
        thermo_mod.set_lid_temperature(lid_temp)

    thermo_mod.set_block_temperature(block_temp,
                                     hold_time_minutes=minutes,
                                     hold_time_seconds=seconds)


def _add_samples(pipette, src_plt, dst_plt, first_col, last_col, vol):
    '''Add samples.'''
    for src_col, dst_col in zip(src_plt.columns()[first_col - 1:last_col],
                                dst_plt.columns()[first_col - 1:last_col]):
        pipette.transfer(vol, src_col, dst_col, mix_after=(1, 5.0))


def _distribute_reagent(pipette, reag_plt, dst_plt, first_col, last_col,
                        reagent, vol):
    '''Distribute reagent.'''
    pipette.pick_up_tip()

    _, reag_well = _get_plate_well(reag_plt, reagent)

    dest_cols = dst_plt.rows_by_name()['A']

    pipette.distribute(vol,
                       reag_plt.wells_by_name()[reag_well],
                       dest_cols[first_col - 1:last_col],
                       new_tip='never')

    pipette.drop_tip()


def _transfer_reagent(pipette, reag_plt, dst_plt, first_col, last_col,
                      reagent, vol):
    '''Transfer reagent.'''
    _, reag_well = _get_plate_well(reag_plt, reagent)

    for dst_col in dst_plt.columns()[first_col - 1:last_col]:
        pipette.transfer(vol, reag_plt[reag_well], dst_col, mix_after=(1, vol))


def _do_pcr(thermo_mod):
    '''Do PCR.'''
    thermo_mod.close_lid()
    thermo_mod.set_lid_temperature(105)
    thermo_mod.set_block_temperature(98, hold_time_seconds=30)

    profile = [
        {'temperature': 98, 'hold_time_seconds': 15},
        {'temperature': 65, 'hold_time_seconds': 5}
    ]

    thermo_mod.execute_profile(steps=profile, repetitions=30,
                               block_max_volume=25)

    thermo_mod.open_lid()


def _get_last_col():
    '''Get last sample column.'''
    return int(_SRC_PLATE['last'][1])


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
