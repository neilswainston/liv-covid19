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

_TIP_RACKS = {
    'type': 'opentrons_96_filtertiprack_20ul',
    'start_at_tip': 'A1'
}

_PIPETTES = {
    'right': 'p50_multi'
}

_REAGENT_PLATE = {
    'type': 'nest_12_reservoir_15ml',
    'components': {'ssiv_buffer': 'A1',
                   'dtt': 'B1',
                   'ribonuclease_inhibitor': 'C1',
                   'reverse_transcriptase': 'D1'}
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
    writer = ProtocolWriter(protocol)
    writer.write()


class ProtocolWriter():
    '''Class to write protocol.'''

    def __init__(self, protocol):
        self.__protocol = protocol

    def write(self):
        '''Write protocol.'''

        # Setup:
        self.__do_setup()

        # Add functions:
        self.__add_funcs()

    def __do_setup(self):
        '''Setup.'''

        # Setup tip racks:
        tip_racks = self.__add_tip_racks()

        # Setup pipettes:
        self.__add_pipettes(tip_racks)

        # Setup plates:
        self.__add_plates()

    def __add_tip_racks(self):
        '''Add tip racks.'''
        tip_racks = {}

        for _ in range(_SRC_PLATES['count']):
            tip_rack = self.__protocol.load_labware(
                _TIP_RACKS['type'],
                self.__next_empty_slot())

            tip_racks[tip_rack] = _TIP_RACKS.get('start_at_tip', 'A1')

        return tip_racks

    def __add_pipettes(self, tip_racks):
        '''Add pipettes.'''
        for mount, instrument_name in _PIPETTES.items():
            pipette = self.__protocol.load_instrument(
                instrument_name, mount, tip_racks=list(tip_racks))

            for tip_rack, start_at_tip in tip_racks.items():
                pipette.starting_tip = tip_rack[start_at_tip]
                break

    def __add_plates(self):
        '''Add plates.'''
        # Add reagent plate:
        self.__protocol.load_labware(_REAGENT_PLATE['type'],
                                     self.__next_empty_slot(),
                                     'reagents')

        # Add source and destination plates:
        for plt_idx in range(_SRC_PLATES['count']):
            self.__protocol.load_labware(_SRC_PLATES['type'],
                                         self.__next_empty_slot(),
                                         'smpl_src_%i' % (plt_idx + 1))

            self.__protocol.load_labware(_SRC_PLATES['type'],
                                         self.__next_empty_slot(),
                                         'smpl_dst_%i' % (plt_idx + 1))

    def __add_funcs(self):
        '''Add functions.'''
        pipette = get_pipette(self.__protocol, channels=8)

        for plt_idx in range(_SRC_PLATES['count']):
            src_plt = get_obj('smpl_src_%i' % (plt_idx + 1),
                              self.__protocol)

            dst_plt = get_obj('smpl_dst_%i' % (plt_idx + 1),
                              self.__protocol)

            for src_col, dst_col in zip(src_plt.columns(), dst_plt.columns()):
                pipette.transfer(5.0, src_col, dst_col)

    def __next_empty_slot(self):
        '''Get next empty slot.'''
        for slot, obj in self.__protocol.deck.items():
            if not obj:
                return slot

        raise IndexError('Insufficient slots on desk')

    def __get_plate_well(self, component):
        '''Get plate well.'''
        if component in _REAGENT_PLATE.get('components', []):
            return get_obj(_REAGENT_PLATE['name'], self.__protocol), \
                _REAGENT_PLATE['components']

        return None


def get_obj(obj_name, protocol):
    '''Get object.'''
    for val in protocol.deck.values():
        if val and val.name == obj_name:
            return val

    return None


def get_pipette(protocol, channels):
    '''Get appropriate pipette for volume.'''

    # Ensure pipette is appropriate for minimum volume:
    valid_pipettes = [pip for pip in protocol.loaded_instruments.values()
                      if pip.channels == channels]

    return valid_pipettes[0] if valid_pipettes else None


def main():
    '''main method.'''
    filename = os.path.realpath(__file__)

    with open(filename) as protocol_file:
        runlog, _ = simulate.simulate(protocol_file, filename)
        print(simulate.format_runlog(runlog))


if __name__ == '__main__':
    main()
