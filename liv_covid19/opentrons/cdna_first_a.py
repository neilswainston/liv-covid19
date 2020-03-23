'''
(c) University of Liverpool 2020

All rights reserved.

@author: neilswainston
'''
# pylint: disable=invalid-name
import os.path

from opentrons import simulate


metadata = {'apiLevel': '2.0',
            'author': 'Neil Swainston <neil.swainston@liverpool.ac.uk>',
            'description': 'simple'}

_TIP_RACK_TYPE = 'opentrons_96_filtertiprack_20ul'

_REAGENT_PLATE = {
    'type': 'nest_12_reservoir_15ml',
    'components': {'primer_mix': 'A1',
                   'rt_reaction_mix': 'B1'}
}

_SRC_PLATES = {
    'count': 1,
    'type': '4ti_96_wellplate_350ul'
}

_DST_PLATES = {
    'type': '4ti_96_wellplate_350ul'
}


def run(protocol):
    '''Run protocol.'''
    assert _SRC_PLATES['count'] < 4

    # Setup tip racks:
    reag_tip_rack, src_tip_racks = _add_tip_racks(protocol)

    # Add pipette:
    pipette = protocol.load_instrument(
        'p50_multi', 'left', tip_racks=list([reag_tip_rack] + src_tip_racks))

    # Setup plates:
    reag_plt = _add_plates(protocol)

    # Add operations:
    _add_operations(protocol, pipette, src_tip_racks, reag_plt)


def _add_tip_racks(protocol):
    '''Add tip racks.'''
    reag_tip_rack = protocol.load_labware(_TIP_RACK_TYPE, 10)

    # Add source and destination tip-racks to deck positions 1 -> n:
    src_tip_racks = [protocol.load_labware(_TIP_RACK_TYPE, idx + 1)
                     for idx in range(_SRC_PLATES['count'])]

    return reag_tip_rack, src_tip_racks


def _add_plates(protocol):
    '''Add plates.'''
    # Add reagent plate:
    reag_plt = protocol.load_labware(_REAGENT_PLATE['type'], 11)

    # Add source and destination plates:
    for plt_idx in range(_SRC_PLATES['count']):
        protocol.load_labware(_SRC_PLATES['type'],
                              plt_idx + 4,
                              'smpl_src_%i' % (plt_idx + 1))

        protocol.load_labware(_DST_PLATES['type'],
                              plt_idx + 7,
                              'smpl_dst_%i' % (plt_idx + 1))

    return reag_plt


def _add_operations(protocol, pipette, src_tip_racks, reag_plt):
    '''Add operations.'''

    # Transfer reagents:
    pipette.pick_up_tip()

    for plt_idx in range(_SRC_PLATES['count']):
        dst_plt = _get_obj(protocol, 'smpl_dst_%i' % (plt_idx + 1))
        _, reag_well = _get_plate_well(reag_plt, 'primer_mix')

        for dst_col in dst_plt.columns():
            pipette.distribute(8.0, reag_plt[reag_well], dst_col,
                               new_tip='never', touch_tip=True)

    pipette.drop_tip()

    # Transfer RNA samples:
    pipette.starting_tip = src_tip_racks[0]['A1']

    for plt_idx in range(_SRC_PLATES['count']):
        src_plt = _get_obj(protocol, 'smpl_src_%i' % (plt_idx + 1))

        for src_col, dst_col in zip(src_plt.columns(), dst_plt.columns()):
            pipette.transfer(5.0, src_col, dst_col, touch_tip=True)


def _get_plate_well(reag_plt, reagent):
    '''Get reagent plate-well.'''
    well = _REAGENT_PLATE['components'].get(reagent, None)

    if well:
        return reag_plt, well

    return None


def _get_obj(protocol, obj_name):
    '''Get object.'''
    for val in protocol.deck.values():
        if val and val.name == obj_name:
            return val

    return None


def main():
    '''main method.'''
    filename = os.path.realpath(__file__)

    with open(filename) as protocol_file:
        runlog, _ = simulate.simulate(protocol_file, filename)
        print(simulate.format_runlog(runlog))


if __name__ == '__main__':
    main()
