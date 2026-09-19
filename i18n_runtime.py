# -*- coding: utf-8 -*-
"""Runtime translation support for StereonetStudio.

The plugin keeps Italian as its source/default language and uses the Qt
translation catalogues in i18n/. A small TS fallback is provided so the
plugin remains usable on installations where Qt Linguist's compiled QM file
is not available yet.
"""

import os

from qgis.PyQt.QtCore import QLocale, QTranslator, QXmlStreamReader


class TsFallbackTranslator(QTranslator):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._messages = {}

    def load_ts(self, path):
        """Load translations from a Qt Linguist TS file.

        QXmlStreamReader is used instead of Python's stdlib XML parser.
        This avoids unsafe XML entity handling and keeps the plugin free
        from additional Python dependencies.
        """
        self._messages.clear()

        if not os.path.isfile(path):
            return False

        reader = QXmlStreamReader()

        try:
            with open(path, 'rb') as ts_file:
                reader.addData(ts_file.read())
        except OSError:
            return False

        current_context = ''

        while not reader.atEnd():
            reader.readNext()

            if reader.isStartElement():
                element_name = reader.name()

                if element_name == 'context':
                    current_context = ''

                elif element_name == 'name' and current_context == '':
                    current_context = reader.readElementText()

                elif element_name == 'message':
                    source = ''
                    translation = ''

                    while not reader.atEnd():
                        reader.readNext()

                        if reader.isStartElement():
                            child_name = reader.name()

                            if child_name == 'source':
                                source = reader.readElementText()

                            elif child_name == 'translation':
                                translation = reader.readElementText()

                        elif (
                            reader.isEndElement()
                            and reader.name() == 'message'
                        ):
                            break

                    if (
                        current_context
                        and source
                        and translation
                        and translation != source
                    ):
                        self._messages[
                            (current_context, source)
                        ] = translation

        if reader.hasError():
            self._messages.clear()
            return False

        return True

    def translate(self, context, sourceText, disambiguation=None, n=-1):
        return self._messages.get((context, sourceText), '')


def load_translator(plugin_dir, app):
    """Install the translator matching QGIS/Qt locale.

    Italian is the source/default language; English uses the English
    catalogue. The QM file is preferred, with TS as a development/runtime
    fallback for systems without a compiled catalogue.
    """
    locale = QLocale.system().name().lower()
    lang = 'it' if locale.startswith('it') else 'en'
    base = os.path.join(
        plugin_dir,
        'i18n',
        'stereonet_studio_' + lang
    )

    translator = QTranslator(app)

    if translator.load(base + '.qm'):
        app.installTranslator(translator)
        return translator

    fallback = TsFallbackTranslator(app)

    if fallback.load_ts(base + '.ts'):
        app.installTranslator(fallback)
        return fallback

    return None
