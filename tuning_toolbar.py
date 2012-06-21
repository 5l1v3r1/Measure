# -*- coding: utf-8 -*-
#! /usr/bin/python
#
# Copyright (C) 2009-12 Walter Bender
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# You should have received a copy of the GNU General Public License
# along with this library; if not, write to the Free Software
# Foundation, 51 Franklin Street, Suite 500 Boston, MA 02110-1335 USA

import gtk
import gobject
import os
from gettext import gettext as _

from config import ICONS_DIR, CAPTURE_GAIN, MIC_BOOST, XO1, XO15, XO175, XO30, \
    INSTRUMENT_DICT

from sugar.graphics.toolbutton import ToolButton
from sugar.graphics.combobox import ComboBox
from sugar.graphics.toolcombobox import ToolComboBox
from sugar.graphics import style
import logging
log = logging.getLogger('measure-activity')
log.setLevel(logging.DEBUG)


NOTES = ['C', 'C♯/D♭', 'D', 'D♯/E♭', 'E', 'F', 'F♯/G♭',
         'G', 'G♯/A♭', 'A', 'A♯/B♭', 'B']
SHARP = '♯'
FLAT = '♭'
A0 = 27.5
C8 = 4186.01
TWELTHROOT2 = 1.05946309435929
COLOR_RED = style.Color('#FF6060')
COLOR_YELLOW = style.Color('#FFFF00')
COLOR_GREEN = style.Color('#00FF00')
SPAN = '<span foreground="%s"><big><b>%s</b></big></span>'


class TuningToolbar(gtk.Toolbar):
    ''' The toolbar for tuning instruments '''

    def __init__(self, activity):
        gtk.Toolbar.__init__(self)

        self.activity = activity
        self._show_tuning_line = False
        self._updating_note = True
        self._tuning_tool = None

        # Set up Instrument Combo box
        self._instrument_combo = ComboBox()
        self.instrument = [_('None')]
        for k in INSTRUMENT_DICT.keys():
            self.instrument.append(k)
        self._instrument_changed_id = self._instrument_combo.connect(
            'changed', self.update_instrument_control)
        for i, s in enumerate(self.instrument):
            self._instrument_combo.append_item(i, s, None)
        self._instrument_combo.set_active(0)
        if hasattr(self._instrument_combo, 'set_tooltip_text'):
            self._instrument_combo.set_tooltip_text(_('Tune an instrument.'))
        self._instrument_tool = ToolComboBox(self._instrument_combo)
        self.insert(self._instrument_tool, -1)

        if self.activity.has_toolbarbox:
            separator = gtk.SeparatorToolItem()
            separator.props.draw = True
            self.insert(separator, -1)

        self._notes_combo = ComboBox()
        n = 0
        for octave in range(9):
            for i in range(len(NOTES)):
                if octave == 0 and i < 9:  # Start with A0
                    continue
                self._notes_combo.append_item(
                    n, note_octave(i, octave), None)
                n += 1
        self._notes_combo.set_active(48) # A4
        self._notes_changed_id = self._notes_combo.connect(
            'changed', self.update_note)
        if hasattr(self._notes_combo, 'set_tooltip_text'):
            self._notes_combo.set_tooltip_text(_('Notes'))
        self._notes_tool = ToolComboBox(self._notes_combo)
        self.insert(self._notes_tool, -1)

        # The entry is used to display a note or for direct user input
        self._freq_entry = gtk.Entry()
        self._freq_entry.set_text('440')  # A
        self._freq_entry_changed_id = self._freq_entry.connect(
            'changed', self.update_freq_entry)
        if hasattr(self._freq_entry, 'set_tooltip_text'):
            self._freq_entry.set_tooltip_text(
                _('Enter a frequency to display.'))
        self._freq_entry.set_width_chars(8)
        self._freq_entry.show()
        toolitem = gtk.ToolItem()
        toolitem.add(self._freq_entry)
        self.insert(toolitem, -1)
        toolitem.show()

        self._new_tuning_line = ToolButton('tuning-tools')
        self._new_tuning_line.show()
        self.insert(self._new_tuning_line, -1)
        self._new_tuning_line.set_tooltip(_('Show tuning line.'))
        self._new_tuning_line.connect('clicked', self.tuning_line_cb)

        if self.activity.has_toolbarbox:
            separator = gtk.SeparatorToolItem()
            separator.props.draw = True
            self.insert(separator, -1)

        self._harmonic = ToolButton('harmonics')
        self._harmonic.show()
        self.insert(self._harmonic, -1)
        self._harmonic.set_tooltip(_('Show harmonics.'))
        self._harmonic.connect('clicked', self.harmonic_cb)

        if self.activity.has_toolbarbox:
            separator = gtk.SeparatorToolItem()
            separator.props.draw = True
            self.insert(separator, -1)

        self._play_tone = ToolButton('media-playback-start')
        self._play_tone.show()
        self.insert(self._play_tone, -1)
        self._play_tone.set_tooltip(_('Play a note.'))
        self._play_tone.connect('clicked', self.play_cb)

        if self.activity.has_toolbarbox:
            separator = gtk.SeparatorToolItem()
            separator.props.draw = False
            separator.set_expand(True)
            self.insert(separator, -1)

        self.label = gtk.Label('')
        self.label.set_use_markup(True)
        self.label.show()
        toolitem = gtk.ToolItem()
        toolitem.add(self.label)
        self.insert(toolitem, -1)
        toolitem.show()

        self.show_all()

    def update_note(self, *args):
        ''' Calculate the frequency based on note combo '''
        if not hasattr(self, '_freq_entry'):  # Still setting up toolbar
            return
        i = self._notes_combo.get_active()
        freq = A0 * pow(TWELTHROOT2, i)
        self._updating_note = True
        self._freq_entry.set_text('%0.3f' % (freq))
        self.label.set_markup(SPAN % (style.COLOR_WHITE.get_html(),
                                      note_octave(index_to_note(i),
                                                  index_to_octave(i))))
        if self._show_tuning_line:
            self.activity.wave.tuning_line = freq
        return

    def update_tuning_control(self, *args):
        ''' Update note '''
        if not hasattr(self, '_freq_entry'):  # Still setting up toolbar?
            return
        instrument = self.instrument[self._instrument_combo.get_active()]
        if not instrument in INSTRUMENT_DICT:
            return
        if self.tuning[self._tuning_combo.get_active()] == _('All notes'):
            self._notes_combo.set_active(
                freq_index(INSTRUMENT_DICT[instrument][0]))
            self.activity.wave.instrument = instrument
            self.activity.wave.tuning_line = 0.0
            self._new_tuning_line.set_icon('tuning-tools')
            self._new_tuning_line.set_tooltip(_('Show tuning line.'))
            self._show_tuning_line = False
        else:
            freq = INSTRUMENT_DICT[instrument][
                self._tuning_combo.get_active() - 1]  # All notes is 0
            self._notes_combo.set_active(
                freq_index(INSTRUMENT_DICT[instrument][
                        self._tuning_combo.get_active() - 1]))
            self.activity.wave.instrument = None
            self.activity.wave.tuning_line = freq
            self._new_tuning_line.set_icon('tuning-tools-off')
            self._new_tuning_line.set_tooltip(_('Hide tuning line.'))
            self._show_tuning_line = True
        self._updating_note = False

    def update_freq_entry(self, *args):
        # Calcualte a note from a frequency
        if not self._updating_note:  # Only if user types in a freq.
            try:
                freq = float(self._freq_entry.get_text())
                # Only consider notes in piano range
                if freq < A0 * 0.97:
                    self.label.set_text('< A0')
                    return
                if freq > C8 * 1.03:
                    self.label.set_text('> C8')
                    return
                for i in range(88):
                    f = A0 * pow(TWELTHROOT2, i)
                    if freq < f * 1.03 and freq > f * 0.97:
                        label = NOTES[index_to_note(i)]
                        # calculate if we are sharp or flat
                        if freq < f * 0.98:
                            label = '%s %s %s' % (FLAT, label, FLAT)
                            self.label.set_markup(SPAN % (
                                    COLOR_RED.get_html(), label))
                        elif freq < f * 0.99:
                            label = '%s %s %s' % (FLAT, label, FLAT)
                            self.label.set_markup(SPAN % (
                                    COLOR_YELLOW.get_html(), label))
                        elif freq > f * 1.02:
                            label = '%s %s %s' % (SHARP, label, SHARP)
                            self.label.set_markup(SPAN % (
                                    COLOR_RED.get_html(), label))
                        elif freq > f * 1.01:
                            label = '%s %s %s' % (SHARP, label, SHARP)
                            self.label.set_markup(SPAN % (
                                    COLOR_YELLOW.get_html(), label))
                        else:
                            self.label.set_markup(SPAN % (
                                    style.COLOR_WHITE.get_html(), label))
                        return
            except ValueError:
                return
        self._updating_note = False

    def update_instrument_control(self, *args):
        ''' Callback for instrument control '''
        instrument = self.instrument[self._instrument_combo.get_active()]
        if self._tuning_tool is not None:
            self.remove(self._tuning_tool)
        if instrument == _('None'):
            self.activity.wave.instrument = None
            return
        self.activity.wave.instrument = instrument

        # Add a Tuning Combo box for this instrument
        self._tuning_combo = ComboBox()
        self.tuning = [_('All notes')]
        for f in INSTRUMENT_DICT[instrument]:
            self.tuning.append(freq_note(f))
        self._tuning_changed_id = self._tuning_combo.connect(
            'changed', self.update_tuning_control)
        for i, s in enumerate(self.tuning):
            self._tuning_combo.append_item(i, s, None)
        self._tuning_combo.set_active(0)
        if hasattr(self._tuning_combo, 'set_tooltip_text'):
            self._tuning_combo.set_tooltip_text(instrument)
        self._tuning_tool = ToolComboBox(self._tuning_combo)
        self.insert(self._tuning_tool, 1)
        self._tuning_combo.show()
        self._tuning_tool.show()
        self.show_all()

    def harmonic_cb(self, *args):
        ''' Callback for harmonics control '''
        self.activity.wave.harmonics = not self.activity.wave.harmonics
        if self.activity.wave.harmonics:
            self._harmonic.set_icon('harmonics-off')
            self._harmonic.set_tooltip(_('Hide harmonics.'))
        else:
            self._harmonic.set_icon('harmonics')
            self._harmonic.set_tooltip(_('Show harmonics.'))

    def tuning_line_cb(self, *args):
        ''' Callback for tuning insert '''
        if self._show_tuning_line:
            self.activity.wave.tuning_line = 0.0
            self._new_tuning_line.set_icon('tuning-tools')
            self._new_tuning_line.set_tooltip(_('Show tuning line.'))
            self._show_tuning_line = False
        else:
            freq = self._freq_entry.get_text()
            try:
                self.activity.wave.tuning_line = float(freq)
                if freq < 0:
                    freq = -freq
                self._new_tuning_line.set_icon('tuning-tools-off')
                self._new_tuning_line.set_tooltip(_('Hide tuning line.'))
                self._show_tuning_line = True
            except ValueError:
                self.activity.wave.tuning_line = 0.0
                self._freq_entry.set_text('0')

    def play_cb(self, *args):
        ''' Play a tone at current frequency '''
        # TODO: pause/restart capture??
        f = float(self._freq_entry.get_text())
        os.system('speaker-test -t sine -l 1 -f %f' % (f))

def note_octave(note, octave):
    if '/' in NOTES[note]:
        flat, sharp = NOTES[note].split('/')
        return '%s%d/%s%d' % (flat, octave, sharp, octave)
    else:
        return '%s%d' % (NOTES[note], octave)

def freq_note(freq):
    for i in range(88):
        f = A0 * pow(TWELTHROOT2, i)
        if freq < f * 1.03 and freq > f * 0.97:  # Found a match
            return note_octave(index_to_note(i), index_to_octave(i))
    return '?'

def freq_index(freq):
    for i in range(88):
        f = A0 * pow(TWELTHROOT2, i)
        if freq < f * 1.03 and freq > f * 0.97:  # Found a match
            return i
    return 0

def index_to_octave(i):
    return int((i - 3) / 12) + 1  # -3 because we start with A

def index_to_note(i):
    return (i-3) % 12  # -3 because we start with A
