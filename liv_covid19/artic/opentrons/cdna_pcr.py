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
    'components': {'primer_mix': 'A1',
                   'rt_reaction_mix': 'A2',
                   'primer_pool_a_mastermix': 'A3',
                   'primer_pool_b_mastermix': 'A4'}
}

_SAMPLE_PLATE_TYPE = '4titude_96_wellplate_200ul'

_SAMPLE_PLATE_LAST = 'H12'

_TEMP_DECK = 'tempdeck'

_VOLS = {
    'primer_mix': 3.0,
    'RNA': 10.0,
    'rt_reaction_mix': 7.0,
    'primer_pool_mastermix': 25.0,
    'cDNA': 5.0
}

# Scale volumes:
_VOL_SCALE = 1.0

_VOLS = {key: vol * _VOL_SCALE for key, vol in _VOLS.items()}


def run(protocol):
    '''Run protocol.'''
    # Setup:
    therm_mod, temp_deck, p10_multi, p300_multi, reag_plt, src_plt, \
        dst_plts = _setup(protocol)

    # cDNA:
    _cdna(protocol, therm_mod, p10_multi, reag_plt, src_plt, dst_plts[0])

    # PCR:
    message = '''
        Remove %s.
        Move %s to %s.
        Add new %s to %s.''' % \
        (src_plt,
         dst_plts[0], temp_deck.labware.parent._display_name,
         dst_plts[0].load_name, therm_mod.labware.parent._display_name)

    if len(dst_plts) > 1:
        message += '''
        Add new %s to %s.
    ''' % (dst_plts[1].load_name, dst_plts[1].parent)

    protocol.pause(message)

    src_plt.name = 'cDNA'
    dst_plts[0].name = 'PCR'

    _pcr(protocol, therm_mod, p10_multi, p300_multi, reag_plt, src_plt,
         dst_plts)


def _setup(protocol, use_temp_deck=False):
    '''Setup.'''
    # Add temp deck:
    therm_mod = protocol.load_module('thermocycler', 7)
    therm_mod.open_lid()
    therm_mod.set_block_temperature(4)
    therm_mod.set_lid_temperature(105)

    temp_deck = protocol.load_module(_TEMP_DECK, 4)

    if use_temp_deck:
        temp_deck.set_temperature(6)

    # Setup tip racks:
    tip_racks_10 = \
        [protocol.load_labware('opentrons_96_filtertiprack_10ul', slot)
         for slot in [1, 2, 3]]

    tip_racks_200 = \
        [protocol.load_labware('opentrons_96_filtertiprack_200ul', 6)]

    # Add pipette:
    p10_multi = protocol.load_instrument(
        'p10_multi', 'left', tip_racks=tip_racks_10)

    p300_multi = protocol.load_instrument(
        'p300_multi', 'right', tip_racks=tip_racks_200)

    # Add reagent plate:
    reag_plt = protocol.load_labware(_REAGENT_PLATE['type'], 5, 'Reagents')

    # Add source and thermo plates:
    src_plt = temp_deck.load_labware(_SAMPLE_PLATE_TYPE, 'RNA')
    dst_plts = [therm_mod.load_labware(_SAMPLE_PLATE_TYPE, 'cDNA')]

    if _get_num_cols() > 6:
        dst_plts.append(
            protocol.load_labware(_SAMPLE_PLATE_TYPE, 9, 'PCR2'))

    return therm_mod, temp_deck, p10_multi, p300_multi, reag_plt, src_plt, \
        dst_plts


def _cdna(protocol, therm_mod, p10_multi, reag_plt, src_plt, dst_plt,
          transfer_samples=False):
    '''Generate cDNA.'''
    protocol.comment('\nGenerate cDNA')

    if transfer_samples:
        # Add primer mix:
        protocol.comment('\nAdd primer mix')

        _distribute_reagent(p10_multi, reag_plt,
                            dst_plt.columns()[:_get_num_cols()],
                            'primer_mix', _VOLS['primer_mix'],
                            disp_bottom=0.5,
                            tip_fate=None)

        # Add RNA samples:
        protocol.comment('\nAdd RNA samples')
        _transfer_samples(p10_multi, src_plt, dst_plt, 1, 1, _VOLS['RNA'])
    else:
        mix_vol = min(_VOLS['primer_mix'] + _VOLS['RNA'],
                      p10_multi.max_volume)

        _transfer_reagent(p10_multi, reag_plt,
                          dst_plt, 1,
                          'primer_mix', _VOLS['primer_mix'],
                          mix_after=(3, mix_vol))

    # Incubate at 65C for 5 minute:
    therm_mod.close_lid()
    _incubate(therm_mod, 65, 5, lid_temp=105)

    # Incubate (on ice) / at min temp for 1 minute:
    _incubate(therm_mod, 4, 1)
    therm_mod.open_lid()

    # Add RT reaction mix:
    protocol.comment('\nAdd RT reaction mix')

    prev_aspirate, prev_dispense, _ = \
        _set_flow_rate(protocol, p10_multi, aspirate=3, dispense=5)

    _transfer_reagent(p10_multi, reag_plt,
                      dst_plt, 1,
                      'rt_reaction_mix', _VOLS['rt_reaction_mix'])

    _set_flow_rate(protocol, p10_multi, aspirate=prev_aspirate,
                   dispense=prev_dispense)

    # Incubate at 42C for 50 minute:
    therm_mod.close_lid()
    _incubate(therm_mod, 42, 50, lid_temp=105)

    # Incubate at 70C for 10 minute:
    _incubate(therm_mod, 70, 10, lid_temp=105)

    # Incubate at 4C for 1 minute:
    _incubate(therm_mod, 4, 1, lid_temp=105)
    therm_mod.open_lid()


def _pcr(protocol, therm_mod, p10_multi, p300_multi, reag_plt, src_plt,
         dst_plts):
    '''Do PCR.'''
    protocol.comment('\nSetup PCR')

    # Add PCR primer mix:
    protocol.comment('\nAdd PCR primer mix')

    prev_aspirate, _, _ = _set_flow_rate(protocol, p300_multi, aspirate=50)

    # Add Pool A:
    a_cols = []
    b_cols = []

    for dst_plt in dst_plts:
        a_cols.extend(dst_plt.columns()[:6])
        b_cols.extend(dst_plt.columns()[6:])

    _distribute_reagent(p300_multi, reag_plt,
                        a_cols[:_get_num_cols()],
                        'primer_pool_a_mastermix',
                        _VOLS['primer_pool_mastermix'] - _VOLS['cDNA'],
                        asp_bottom=1.5, disp_bottom=1.5)

    # Add Pool B:
    _distribute_reagent(p300_multi, reag_plt,
                        b_cols[:_get_num_cols()],
                        'primer_pool_b_mastermix',
                        _VOLS['primer_pool_mastermix'] - _VOLS['cDNA'],
                        asp_bottom=1.5, disp_bottom=1.5)

    _set_flow_rate(protocol, p300_multi, aspirate=prev_aspirate)

    # Add samples to each pool:
    protocol.comment('\nSplit samples into pools A and B')

    for col_idx in range(_get_num_cols()):
        plt_idx = col_idx // 6
        # print(plt_idx, col_idx, dst_plts[plt_idx])
        dst_cols = [dst_plts[plt_idx].columns()[col_idx % 6]] + \
                   [dst_plts[plt_idx].columns()[col_idx % 6 + 6]]

        p10_multi.distribute(
            _VOLS['cDNA'],
            src_plt.columns()[col_idx],
            dst_cols,
            mix_after=(3, _VOLS['cDNA']),
            disposal_volume=0)

    # PCR:
    if len(dst_plts) > 1:
        protocol.pause('''
        Move %s to external PCR machine and run PCR protocol.
        ''' % dst_plts[1])

    protocol.comment('\nPerform PCR')
    _do_pcr(therm_mod)

    # Incubate at 4C for 1 minute:
    _incubate(therm_mod, 4, 1)

    therm_mod.deactivate_lid()


def _do_pcr(therm_mod):
    '''Do PCR.'''
    therm_mod.close_lid()
    therm_mod.set_lid_temperature(105)
    therm_mod.set_block_temperature(98, hold_time_seconds=30)

    profile = [
        {'temperature': 98, 'hold_time_seconds': 15},
        {'temperature': 63, 'hold_time_minutes': 5}
    ]

    therm_mod.execute_profile(steps=profile, repetitions=35,
                              block_max_volume=25)


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


def _distribute_reagent(pipette, reag_plt, dest_cols,
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

    asp_well = reag_plt.wells_by_name()[reag_well]

    _distribute(pipette,
                asp_well.top(asp_top) if asp_top is not None
                else (asp_well.bottom(asp_bottom)
                      if asp_bottom is not None
                      else asp_well),
                [dest_col[0].top(disp_top) if disp_top is not None
                 else (dest_col[0].bottom(disp_bottom)
                       if disp_bottom is not None
                       else dest_col[0])
                 for dest_col in dest_cols],
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
