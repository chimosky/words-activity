# Copyright 2008 Chris Ball.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

"""Words Activity: A multi-lingual dictionary with speech synthesis."""
"""Actividad Palabras: Un diccionario multi-lengua con sintesis de habla"""

from gi.repository import GObject
from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import Pango

import logging
import os
import subprocess

from gettext import gettext as _

from sugar3.activity import activity
from sugar3.graphics.icon import Icon
from sugar3.graphics.toolbarbox import ToolbarBox
from sugar3.activity.widgets import ActivityToolbarButton
from sugar3.activity.widgets import StopButton
from sugar3.graphics import style
from sugar3.graphics.palettemenu import PaletteMenuItem
from sugar3.graphics.palette import Palette
from sugar3.graphics.palette import ToolInvoker

import dictdmodel


class FilterToolItem(Gtk.ToolButton):

    _LABEL_MAX_WIDTH = 18
    _MAXIMUM_PALETTE_COLUMNS = 4

    __gsignals__ = {
        'changed': (GObject.SignalFlags.RUN_LAST, None, ([str])), }

    def __init__(self, default_icon, default_value, options):
        self._palette_invoker = ToolInvoker()
        self._options = options
        Gtk.ToolButton.__init__(self)
        logging.error('filter options %s', options)
        self._value = default_value
        self._label = self._options[default_value]
        self.set_is_important(True)
        self.set_size_request(style.GRID_CELL_SIZE, -1)

        self._label_widget = Gtk.Label()
        self._label_widget.set_alignment(0.0, 0.5)
        self._label_widget.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        self._label_widget.set_max_width_chars(self._LABEL_MAX_WIDTH)
        self._label_widget.set_use_markup(True)
        self._label_widget.set_markup(self._label)
        self.set_label_widget(self._label_widget)
        self._label_widget.show()

        self.set_widget_icon(icon_name=default_icon)

        self._hide_tooltip_on_click = True
        self._palette_invoker.attach_tool(self)
        self._palette_invoker.props.toggle_palette = True
        self._palette_invoker.props.lock_palette = True

        self.palette = Palette(_('Select language'))
        self.palette.set_invoker(self._palette_invoker)

        self.props.palette.set_content(self.set_palette_list(options))

    def set_options(self, options):
        self._options = options
        self.palette = Palette(_('Select language'))
        self.palette.set_invoker(self._palette_invoker)
        self.props.palette.set_content(self.set_palette_list(options))
        if self._value not in self._options.keys():
            new_value = self._options.keys()[0]
            self._value = new_value
            self._set_widget_label(self._options[new_value])
            self.emit('changed', new_value)

    def set_widget_icon(self, icon_name=None):
        icon = Icon(icon_name=icon_name,
                    icon_size=style.SMALL_ICON_SIZE)
        self.set_icon_widget(icon)
        icon.show()

    def _set_widget_label(self, label=None):
        # FIXME: Ellipsis is not working on these labels.
        if label is None:
            label = self._label
        if len(label) > self._LABEL_MAX_WIDTH:
            label = label[0:7] + '...' + label[-7:]
        self._label_widget.set_markup(label)
        self._label = label

    def __destroy_cb(self, icon):
        if self._palette_invoker is not None:
            self._palette_invoker.detach()

    def create_palette(self):
        return None

    def get_palette(self):
        return self._palette_invoker.palette

    def set_palette(self, palette):
        self._palette_invoker.palette = palette

    palette = GObject.property(
        type=object, setter=set_palette, getter=get_palette)

    def get_palette_invoker(self):
        return self._palette_invoker

    def set_palette_invoker(self, palette_invoker):
        self._palette_invoker.detach()
        self._palette_invoker = palette_invoker

    palette_invoker = GObject.property(
        type=object, setter=set_palette_invoker, getter=get_palette_invoker)

    def do_draw(self, cr):
        if self.palette and self.palette.is_up():
            allocation = self.get_allocation()
            # draw a black background, has been done by the engine before
            cr.set_source_rgb(0, 0, 0)
            cr.rectangle(0, 0, allocation.width, allocation.height)
            cr.paint()

        Gtk.ToolButton.do_draw(self, cr)

        if self.palette and self.palette.is_up():
            invoker = self.palette.props.invoker
            invoker.draw_rectangle(cr, self.palette)

        return False

    def set_palette_list(self, options):
        _menu_item = PaletteMenuItem(text_label=options[options.keys()[0]])
        req2 = _menu_item.get_preferred_size()[1]
        menuitem_width = req2.width
        menuitem_height = req2.height

        palette_width = Gdk.Screen.width() - style.GRID_CELL_SIZE
        palette_height = Gdk.Screen.height() - style.GRID_CELL_SIZE * 3

        nx = min(self._MAXIMUM_PALETTE_COLUMNS,
                 int(palette_width / menuitem_width))
        ny = min(int(palette_height / menuitem_height), len(options) + 1)
        if ny >= len(options):
            nx = 1
            ny = len(options)

        grid = Gtk.Grid()
        grid.set_row_spacing(style.DEFAULT_PADDING)
        grid.set_column_spacing(0)
        grid.set_border_width(0)
        grid.show()

        x = 0
        y = 0

        for key in options.keys():
            menu_item = PaletteMenuItem()
            menu_item.set_label(options[key])

            menu_item.set_size_request(style.GRID_CELL_SIZE * 3, -1)

            menu_item.connect('button-release-event', self._option_selected,
                              key)
            grid.attach(menu_item, x, y, 1, 1)
            x += 1
            if x == nx:
                x = 0
                y += 1

            menu_item.show()

        if palette_height < (y * menuitem_height + style.GRID_CELL_SIZE):
            # if the grid is bigger than the palette, put in a scrolledwindow
            scrolled_window = Gtk.ScrolledWindow()
            scrolled_window.set_policy(Gtk.PolicyType.NEVER,
                                       Gtk.PolicyType.AUTOMATIC)
            scrolled_window.set_size_request(nx * menuitem_width,
                                             (ny + 1) * menuitem_height)
            scrolled_window.add_with_viewport(grid)
            return scrolled_window
        else:
            return grid

    def _option_selected(self, menu_item, event, key):
        self._set_widget_label(self._options[key])
        self._value = key
        self.emit('changed', key)


class WordsActivity(activity.Activity):
    """Words Activity as specified in activity.info"""

    def __init__(self, handle):
        """Set up the Words activity."""
        super(WordsActivity, self).__init__(handle)

        self._dictd_data_dir = './dictd/'
        self._dictionaries = dictdmodel.Dictionaries(self._dictd_data_dir)

        self._from_languages = self._dictionaries.get_languages_from()
        self._from_lang_options = {}
        for lang in self._from_languages:
            self._from_lang_options[lang] = dictdmodel.lang_codes[lang]

        self.max_participants = 1

        toolbar_box = ToolbarBox()

        activity_button = ActivityToolbarButton(self)
        toolbar_box.toolbar.insert(activity_button, 0)
        activity_button.show()

        toolbar_box.toolbar.insert(Gtk.SeparatorToolItem(), -1)

        from_toolitem = Gtk.ToolItem()
        from_toolitem.add(Gtk.Label(_('From:')))
        from_toolitem.show_all()
        toolbar_box.toolbar.insert(from_toolitem, -1)

        self._default_from_language = 'eng'
        self._default_to_language = 'spa'

        # Initial values | Valores iniciales
        self.fromlang = self._default_from_language
        self.tolang = self._default_to_language
        self._dictionary = dictdmodel.Dictionary(self._dictd_data_dir,
                                                 self.fromlang,
                                                 self.tolang)
        self._from_button = FilterToolItem('go-down',
                                           self._default_from_language,
                                           self._from_lang_options)
        self._from_button.connect("changed", self.__from_language_changed_cb)
        toolbar_box.toolbar.insert(self._from_button, -1)

        to_toolitem = Gtk.ToolItem()
        to_toolitem.add(Gtk.Label('    ' + _('To:')))
        to_toolitem.show_all()
        toolbar_box.toolbar.insert(to_toolitem, -1)

        self._init_to_language()
        self._to_button = FilterToolItem('go-down',
                                         self.tolang,
                                         self._to_lang_options)
        self._to_button.connect("changed", self.__to_language_changed_cb)
        toolbar_box.toolbar.insert(self._to_button, -1)

        separator = Gtk.SeparatorToolItem()
        separator.props.draw = False
        separator.set_expand(True)
        toolbar_box.toolbar.insert(separator, -1)
        separator.show()

        stop_button = StopButton(self)
        toolbar_box.toolbar.insert(stop_button, -1)
        stop_button.show()

        self.set_toolbar_box(toolbar_box)
        toolbar_box.show()

        font = Pango.FontDescription("Sans 14")

        # This box will change the orientaion when the screen rotates
        self._big_box = Gtk.Box(Gtk.Orientation.HORIZONTAL)
        self._big_box.set_homogeneous(True)

        lang1_container = Gtk.Grid()
        lang1_container.set_row_spacing(style.DEFAULT_SPACING)
        lang1_container.set_border_width(style.DEFAULT_SPACING)

        self._big_box.pack_start(lang1_container, True, True, 0)

        # Labels
        label1 = Gtk.Label(label=_("Word") + ':')
        label1.modify_font(font)
        label1.set_halign(Gtk.Align.START)
        lang1_container.attach(label1, 0, 0, 2, 1)

        # Text entry box to enter word to be translated
        self.totranslate = Gtk.Entry()
        self.totranslate.set_max_length(50)
        self.totranslate.connect("changed", self.__totranslate_changed_cb)
        self.totranslate.modify_font(font)
        self.totranslate.set_hexpand(True)

        lang1_container.attach(self.totranslate, 0, 1, 1, 1)

        speak1 = Gtk.ToolButton()
        speak1.set_icon_widget(Icon(icon_name='microphone'))
        speak1.connect("clicked", self.speak1_cb)

        lang1_container.attach(speak1, 1, 1, 1, 1)

        label1 = Gtk.Label(label=_("Suggestions") + ':')
        label1.set_halign(Gtk.Align.START)
        lang1_container.attach(label1, 0, 2, 2, 1)

        # The "lang1" treeview box
        self._suggestions_model = Gtk.ListStore(str)
        suggest_treeview = Gtk.TreeView(self._suggestions_model)
        suggest_treeview.modify_font(font)

        suggest_treeview.set_headers_visible(False)
        lang1cell = Gtk.CellRendererText()
        lang1cell.props.ellipsize_set = True
        lang1cell.props.ellipsize = Pango.EllipsizeMode.END
        lang1treecol = Gtk.TreeViewColumn("", lang1cell, text=0)
        self._suggestion_changed_cb_id = suggest_treeview.connect(
            'cursor-changed', self.__suggestion_selected_cb)
        suggest_treeview.append_column(lang1treecol)
        scroll = Gtk.ScrolledWindow(hadjustment=None, vadjustment=None)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(suggest_treeview)
        scroll.set_vexpand(True)
        lang1_container.attach(scroll, 0, 3, 2, 1)

        # This container have the result data
        result_container = Gtk.Grid()
        result_container.set_row_spacing(style.DEFAULT_SPACING)
        result_container.set_border_width(style.DEFAULT_SPACING)
        self._big_box.pack_start(result_container, True, True, 0)

        label2 = Gtk.Label(label=_("Translation") + ':')
        label2.modify_font(font)
        label2.set_halign(Gtk.Align.START)
        result_container.attach(label2, 0, 0, 2, 1)

        # Text entry box to receive word translated

        self.translated = Gtk.TextView()
        self.translated.modify_font(font)
        text_buffer = Gtk.TextBuffer()
        self.translated.set_buffer(text_buffer)
        self.translated.set_left_margin(style.DEFAULT_PADDING)
        self.translated.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.translated.set_editable(False)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC,
                            Gtk.PolicyType.AUTOMATIC)
        scrolled.add(self.translated)

        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)

        result_container.attach(scrolled, 0, 1, 1, 1)

        speak2 = Gtk.ToolButton()
        speak2.set_icon_widget(Icon(icon_name='microphone'))
        speak2.connect("clicked", self.speak2_cb)
        result_container.attach(speak2, 1, 1, 1, 1)

        self._big_box.show_all()
        self.set_canvas(self._big_box)
        self.totranslate.grab_focus()
        self.show_all()

    def __from_language_changed_cb(self, widget, value):
        logging.error('selected translate from %s', value)
        self.fromlang = value
        self._init_to_language()
        logging.error('destination languages %s', self._to_lang_options)
        self._to_button.set_options(self._to_lang_options)
        self._translate()

    def __to_language_changed_cb(self, widget, value):
        logging.error('selected translate to %s', value)
        self.tolang = value
        self._translate()

    def _init_to_language(self):
        self._to_languages = self._dictionaries.get_languages_to(
            self.fromlang)
        self._to_lang_options = {}
        for lang in self._to_languages:
            self._to_lang_options[lang] = dictdmodel.lang_codes[lang]

    def _say(self, text, lang):

        tmpfile = "/tmp/something.wav"
        subprocess.call(["espeak", text, "-w", tmpfile, "-v",
                         dictdmodel.espeak_voices[lang]])
        subprocess.call(["aplay", tmpfile])
        os.unlink(tmpfile)

    def __suggestion_selected_cb(self, treeview):
        model, treeiter = treeview.get_selection().get_selected()
        if treeiter is not None:
            value = model.get_value(treeiter, 0)
            treeview.handler_block(self._suggestion_changed_cb_id)
            self.totranslate.set_text(value)
            treeview.handler_unblock(self._suggestion_changed_cb_id)

    def lang2sel_cb(self, column):
        model, _iter = column.get_selected()
        value = model.get_value(_iter, 0)
        translations = self.languagemodel.GetTranslations(1, value)
        self.translated.set_text(",".join(translations))

    def speak1_cb(self, button):
        text = self.totranslate.get_text()
        lang = self.fromlang
        self._say(text, lang)

    def speak2_cb(self, button):
        text = self.translated.get_text()
        lang = self.tolang
        self._say(text, lang)

    def __totranslate_changed_cb(self, totranslate):
        entry = totranslate.get_text()

        self._suggestions_model.clear()
        if not entry:
            self.translated.set_text('')
            return
        self._translate()

    def _translate(self):
        text = self.totranslate.get_text()
        if not text:
            return

        # verify if the languagemodel is right
        if self._dictionary.get_from_lang() != self.fromlang or \
                self._dictionary.get_to_lang() != self.tolang:
            self._dictionary = dictdmodel.Dictionary(self._dictd_data_dir,
                                                     self.fromlang,
                                                     self.tolang)

        # Ask for completion suggestions
        list1 = self._dictionary.get_suggestions(text)

        for x in list1:
            self._suggestions_model.append([x])

        translations = self._dictionary.get_definition(text)

        self.translated.get_buffer().set_text(''.join(translations))
