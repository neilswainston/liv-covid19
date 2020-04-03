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
                   'rt_reaction_mix': 'A2'}
}

_SAMPLE_PLATE = {
    'type': '4titude_96_wellplate_200ul',
    'last': ['H12', 'H12']
}


def run(protocol):
    '''Run protocol.'''
    # Setup:
    therm_mod, temp_deck, p10_multi, reag_plt, src_plts, therm_plts = _setup(
        protocol)

    # cDNA:
    _cdna(protocol, therm_mod, temp_deck, p10_multi, reag_plt, src_plts,
          therm_plts)


def _setup(protocol):
    '''Setup.'''
    assert len(_SAMPLE_PLATE['last']) < 3

    # Add temp deck:
    therm_mod = protocol.load_module('thermocycler', 7)
    therm_mod.open_lid()
    therm_mod.set_block_temperature(4)
    therm_mod.set_lid_temperature(105)

    # Setup tip racks:
    tip_racks_10 = \
        [protocol.load_labware('opentrons_96_filtertiprack_10ul', slot)
         for slot in [3, 6, 9]]

    # Add pipette:
    p10_multi = protocol.load_instrument(
        'p10_multi', 'left', tip_racks=tip_racks_10)

    # Add reagent plate:
    reag_plt = protocol.load_labware(_REAGENT_PLATE['type'], 5, 'Reagents')

    # Add source and thermo plates:
    src_plts = [protocol.load_labware(_SAMPLE_PLATE['type'], 2, 'RNA')]
    dst_plts = [therm_mod.load_labware(_SAMPLE_PLATE['type'], 'cDNA')]

    if len(_SAMPLE_PLATE['last']) == 2:
        src_plts.append(protocol.load_labware(
            _SAMPLE_PLATE['type'], 1, 'RNA2'))

        temp_deck = protocol.load_module('tempdeck', 4)
        temp_deck.set_temperature(4)

        dst_plts.append(temp_deck.load_labware(_SAMPLE_PLATE['type'], 'cDNA2'))
    else:
        temp_deck = None

    return therm_mod, temp_deck, p10_multi, reag_plt, src_plts, dst_plts


def _cdna(protocol, therm_mod, temp_deck, p10_multi, reag_plt, src_plts,
          dst_plts):
    '''Generate cDNA.'''
    protocol.comment('\nGenerate cDNA')

    # Add primer mix:
    protocol.comment('\nAdd primer mix')
    _distribute_reagent(p10_multi, reag_plt, dst_plts, [1], 'primer_mix', 8.0)

    # Add RNA samples:
    protocol.comment('\nAdd RNA samples')
    _transfer_samples(p10_multi, src_plts, dst_plts, 1, 1, 5.0)

    # Incubate at 65C for 5 minute:
    therm_mod.close_lid()
    _incubate(therm_mod, temp_deck, 65, 5, lid_temp=105)

    # Incubate (on ice) / at min temp for 1 minute:
    _incubate(therm_mod, temp_deck, 8, 1)
    therm_mod.open_lid()

    # Add RT reaction mix:
    protocol.comment('\nAdd RT reaction mix')
    _distribute_reagent(p10_multi, reag_plt, dst_plts, [1], 'rt_reaction_mix',
                        7.0)

    # Incubate at 42C for 10 minute:
    therm_mod.close_lid()
    _incubate(therm_mod, temp_deck, 42, 50, lid_temp=105)

    # Incubate at 70C for 10 minute:
    _incubate(therm_mod, temp_deck, 70, 10, lid_temp=105)

    # Incubate at 4C for 1 minute:
    _incubate(therm_mod, temp_deck, 8, 1, lid_temp=105)
    therm_mod.open_lid()


def _incubate(therm_mod, temp_deck, block_temp, minutes, seconds=0,
              lid_temp=None):
    '''Incubate.'''
    if lid_temp and therm_mod.lid_temperature != lid_temp:
        therm_mod.set_lid_temperature(lid_temp)

    temp_deck.set_temperature(block_temp)

    therm_mod.set_block_temperature(block_temp,
                                    hold_time_minutes=minutes,
                                    hold_time_seconds=seconds)


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
    return [int(well[1:]) for well in _SAMPLE_PLATE['last']]


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
