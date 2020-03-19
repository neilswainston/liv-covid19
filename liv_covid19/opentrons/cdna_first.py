'''
(c) University of Liverpool 2020

All rights reserved.

@author: neilswainston
'''
# pylint: disable=invalid-name
# pylint: disable=protected-access
# pylint: disable=too-few-public-methods
import os.path

from opentrons import simulate


metadata = {'apiLevel': '2.0',
            'author': 'Neil Swainston <neil.swainston@liverpool.ac.uk>',
            'description': 'simple'}

_REAGENT_PLATE = {
    'type': 'nest_12_reservoir_15ml',
    'components': {'primer_mix': 'A1'}
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
    reag_tip_rack = protocol.load_labware(
        'opentrons_96_filtertiprack_20ul', 10)

    # Add source and destination tip-racks to deck positions 1 -> n:
    src_tip_racks = [protocol.load_labware(
        'opentrons_96_filtertiprack_20ul', idx + 1)
        for idx in range(_SRC_PLATES['count'])]

    # Add pipette:
    pipette = protocol.load_instrument(
        'p50_multi', 'left', tip_racks=list([reag_tip_rack] + src_tip_racks))

    # Setup plates:
    _add_plates(protocol)

    # Add operations:
    add_operations(protocol, pipette, src_tip_racks)


def add_operations(protocol, pipette, src_tip_racks):
    '''Add operations.'''
    for plt_idx in range(_SRC_PLATES['count']):
        # Transfer reagents:
        dst_plt = _get_obj(protocol, 'smpl_dst_%i' % (plt_idx + 1))
        reag_plt, reag_well = _get_plate_well(protocol, 'primer_mix')

        pipette.distribute(8.0,
                           reag_plt[reag_well],
                           dst_plt.wells())

        # Transfer RNA samples:
        pipette.starting_tip = src_tip_racks[0]['A1']

        src_plt = _get_obj(protocol, 'smpl_src_%i' % (plt_idx + 1))

        for src_col, dst_col in zip(src_plt.columns(), dst_plt.columns()):
            pipette.transfer(5.0, src_col, dst_col)


def _add_plates(protocol):
    '''Add plates.'''
    # Add reagent plate:
    protocol.load_labware(_REAGENT_PLATE['type'], 11, 'reagent_plt')

    # Add source and destination plates:
    for plt_idx in range(_SRC_PLATES['count']):
        protocol.load_labware(_SRC_PLATES['type'],
                              plt_idx + 4,
                              'smpl_src_%i' % (plt_idx + 1))

        protocol.load_labware(_DST_PLATES['type'],
                              plt_idx + 7,
                              'smpl_dst_%i' % (plt_idx + 1))


def _get_plate_well(protocol, reagent):
    '''Get reagent plate-well.'''
    well = _REAGENT_PLATE['components'].get(reagent, None)

    if well:
        return _get_obj(protocol, 'reagent_plt'), well

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
